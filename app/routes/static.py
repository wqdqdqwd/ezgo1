from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

router = APIRouter()

# Static files mount
router.mount("/static", StaticFiles(directory="static"), name="static")

@router.get("/", response_class=HTMLResponse)
async def read_root():
    """Ana sayfa"""
    return FileResponse("static/index.html")

@router.get("/login", response_class=HTMLResponse)
async def read_login():
    """Login sayfası"""
    return FileResponse("static/login.html")

@router.get("/register", response_class=HTMLResponse)
async def read_register():
    """Register sayfası"""
    return FileResponse("static/register.html")

@router.get("/dashboard", response_class=HTMLResponse)
async def read_dashboard():
    """Dashboard sayfası"""
    return FileResponse("static/dashboard.html")

@router.get("/admin", response_class=HTMLResponse)
async def read_admin():
    """Admin sayfası"""
    return FileResponse("static/admin.html")

@router.get("/{full_path:path}")
async def catch_all(full_path: str):
    """SPA routing için catch-all"""
    # Eğer dosya static klasöründe varsa onu döndür
    static_file_path = f"static/{full_path}"
    if os.path.exists(static_file_path) and os.path.isfile(static_file_path):
        return FileResponse(static_file_path)
    
    # Aksi halde ana sayfayı döndür
    return FileResponse("static/index.html")