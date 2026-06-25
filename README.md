Todo-REST-API-FastAPI-PostgreSQL-Redis
- Built a full-featured CRUD REST API using FastAPI and PostgreSQL with SQLAlchemy ORM,
  implementing JWT-based authentication for secure user registration and login
- Designed user-scoped data access ensuring each authenticated user can only access,
  modify, or delete their own records, with bcrypt password hashing for credential security
- Implemented pagination, keyword search, multi-field filtering, and dynamic sorting on
  list endpoints to handle large datasets efficiently
- Integrated Redis caching to reduce database load on frequently accessed endpoints,
  improving response times for repeated requests, with cache invalidation on data updates
- Structured the codebase with separation of concerns (models, schemas, auth, database
  layers) following REST API best practices 😀
