# How to run overtourism frontend

The frontend web application is built as an Angular single-page app. The repository is available at:

```bash
https://github.com/tn-aixpa/overtourism-frontend
```

Run the frontend container by pointing `API_BASE_URL` at the tenant-scoped v1 backend base path:

```bash
docker run -p 8080:8080 -e API_BASE_URL=https://your-api-url.com/api/v1/molveno tn-aixpa/overtourism-frontend
```

Replace `molveno` with the tenant you want the frontend to work against.
