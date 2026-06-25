from fastapi import FastAPI, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from database import engine, get_db, Base
from models import Todo, User
from auth import hash_password, verify_password, create_access_token, get_current_user
from schemas import (TodoCreate, TodoUpdate, TodoResponse,
                     RegisterRequest, LoginRequest, TokenResponse, UserResponse)
import json                          
from redis_client import get_redis   

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Todo API with JWT Auth", description="Full CRUD Todo App")


# ─────────────────────────────────────────────
# AUTH ROUTES (unchanged)
# ─────────────────────────────────────────────

@app.post("/register", response_model=UserResponse, status_code=201)
def register(user: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = User(
        name=user.name,
        email=user.email,
        password=hash_password(user.password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    token = create_access_token(data={"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}


@app.get("/me", response_model=UserResponse)
def get_my_profile(current_user: User = Depends(get_current_user)):
    return current_user


# ─────────────────────────────────────────────
# FILTER (unchanged)
# ─────────────────────────────────────────────

@app.get("/todos/filter/status", response_model=List[TodoResponse])
def filter_todos(
    completed: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Todo).filter(
        Todo.owner_id == current_user.id,
        Todo.completed == completed
    ).all()


# ─────────────────────────────────────────────
# GET ALL — ✅ REDIS CACHING ADDED HERE
# ─────────────────────────────────────────────

@app.get("/todos")
def get_my_todos(
    page:      int            = Query(default=1,   ge=1,   description="Page number"),
    limit:     int            = Query(default=10,  le=100, description="Items per page"),
    completed: Optional[bool] = Query(default=None,        description="Filter by status"),
    search:    Optional[str]  = Query(default=None,        description="Search title/description"),
    order_by:  str            = Query(default="created_at",description="Sort: created_at or title"),
    order:     str            = Query(default="desc",      description="Direction: asc or desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # ✅ ADDED: build a unique cache key from every query param
    cache_key = f"todos:{current_user.id}:{page}:{limit}:{completed}:{search}:{order_by}:{order}"
    r = get_redis()

    # ✅ ADDED: Step 1 — check cache first
    cached = r.get(cache_key)
    if cached:
        print(f"✅ Cache HIT — {cache_key}")
        return json.loads(cached)        # return immediately, no DB call

    # ✅ ADDED: cache miss — fall through to DB query as normal
    print(f"❌ Cache MISS — {cache_key}")

    # everything below is UNCHANGED — same query as before
    query = db.query(Todo).filter(Todo.owner_id == current_user.id)

    if search:
        keyword = f"%{search}%"
        query = query.filter(
            or_(
                Todo.title.ilike(keyword),
                Todo.description.ilike(keyword)
            )
        )

    if completed is not None:
        query = query.filter(Todo.completed == completed)

    sort_column = Todo.title if order_by == "title" else Todo.created_at
    query = query.order_by(sort_column.asc() if order == "asc" else sort_column.desc())

    total = query.count()
    todos = query.offset((page - 1) * limit).limit(limit).all()

    result = {
        "page":        page,
        "limit":       limit,
        "total":       total,
        "total_pages": (total + limit - 1) // limit,
        "has_next":    page * limit < total,
        "has_prev":    page > 1,
        # ✅ CHANGED: serialize todos so json.dumps works
        "results": [TodoResponse.model_validate(t).model_dump(mode="json") for t in todos]
    }

    # ✅ ADDED: Step 3 — store result in cache for 60 seconds
    r.setex(cache_key, 60, json.dumps(result))

    return result


# ─────────────────────────────────────────────
# CREATE (unchanged)
# ─────────────────────────────────────────────

@app.post("/todos", response_model=TodoResponse, status_code=201)
def create_todo(
    todo: TodoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_todo = Todo(**todo.model_dump(), owner_id=current_user.id)
    db.add(new_todo)
    db.commit()
    db.refresh(new_todo)
    return new_todo


# ─────────────────────────────────────────────
# GET ONE — ✅ REDIS CACHING ADDED HERE
# ─────────────────────────────────────────────

@app.get("/todos/{id}", response_model=TodoResponse)
def get_todo(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # ✅ ADDED: unique key per user per todo id
    cache_key = f"todo:{current_user.id}:{id}"
    r = get_redis()

    # ✅ ADDED: Step 1 — check cache first
    cached = r.get(cache_key)
    if cached:
        print(f"✅ Cache HIT — {cache_key}")
        return json.loads(cached)        # return immediately, no DB call

    # ✅ ADDED: cache miss — go to DB
    print(f"❌ Cache MISS — {cache_key}")

    # UNCHANGED — same DB query as before
    todo = db.query(Todo).filter(Todo.id == id, Todo.owner_id == current_user.id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    # ✅ ADDED: Step 3 — store in cache for 5 minutes
    todo_data = TodoResponse.model_validate(todo).model_dump(mode="json")
    r.setex(cache_key, 300, json.dumps(todo_data))

    return todo


# ─────────────────────────────────────────────
# UPDATE — ✅ CACHE INVALIDATION ADDED HERE
# ─────────────────────────────────────────────

@app.put("/todos/{id}", response_model=TodoResponse)
def update_todo(
    id: int,
    updated: TodoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    todo = db.query(Todo).filter(Todo.id == id, Todo.owner_id == current_user.id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    # UNCHANGED — same update logic
    for key, value in updated.model_dump(exclude_unset=True).items():
        setattr(todo, key, value)
    db.commit()
    db.refresh(todo)

    # ✅ ADDED: delete stale cache so next GET fetches fresh data
    r = get_redis()
    r.delete(f"todo:{current_user.id}:{id}")           # delete this specific todo
    for key in r.scan_iter(f"todos:{current_user.id}:*"):  # delete all list caches
        r.delete(key)

    return todo


# ─────────────────────────────────────────────
# MARK COMPLETE — ✅ CACHE INVALIDATION ADDED HERE
# ─────────────────────────────────────────────

@app.patch("/todos/{id}/complete", response_model=TodoResponse)
def mark_complete(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    todo = db.query(Todo).filter(Todo.id == id, Todo.owner_id == current_user.id).first()
    if not todo:
        raise HTTPException(status_code=404, detail=f"Todo with id {id} not found")

    # UNCHANGED
    todo.completed = True
    db.commit()
    db.refresh(todo)

    # ✅ ADDED: todo changed — delete its cache
    r = get_redis()
    r.delete(f"todo:{current_user.id}:{id}")
    for key in r.scan_iter(f"todos:{current_user.id}:*"):
        r.delete(key)

    return todo


# ─────────────────────────────────────────────
# DELETE — ✅ CACHE INVALIDATION ADDED HERE
# ─────────────────────────────────────────────

@app.delete("/todos/{id}")
def delete_todo(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    todo = db.query(Todo).filter(Todo.id == id, Todo.owner_id == current_user.id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    # UNCHANGED
    db.delete(todo)
    db.commit()

    # ✅ ADDED: todo deleted — remove from cache
    r = get_redis()
    r.delete(f"todo:{current_user.id}:{id}")
    for key in r.scan_iter(f"todos:{current_user.id}:*"):
        r.delete(key)

    return {"message": f"Todo {id} deleted"}