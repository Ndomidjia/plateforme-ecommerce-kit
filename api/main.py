"""API FastAPI : authentification JWT, RBAC (admin/analyst), endpoints analytics et RGPD."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import admin, analytics, auth, rgpd

app = FastAPI(
    title="Plateforme e-commerce — API",
    description="Analyse comportementale et recommandation marketing (RFM, market basket, "
                "funnel, reco collaborative, scoring churn) + endpoints RGPD.",
)

# Dashboard React en dev (Vite) : origine distincte (port 5173), donc CORS
# explicite nécessaire pour que le navigateur autorise les appels à l'API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(analytics.router)
app.include_router(rgpd.router)
app.include_router(admin.router)

@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
