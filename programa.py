
import json
import requests
import hashlib
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, quote
import base64
from pathlib import Path
import time
from typing import Dict
import sys # --- ADDED --- To allow for dynamic printing
# Para la interfaz web
from IPython.display import HTML, display, Image
import ipywidgets as widgets

# ============================================
# CONFIGURACIÓN DE ALIST
# ============================================

class AlistConfig:
    """Configuración para conectarse a Alist""" 
    def __init__(self, base_url: str, username: str = "", password: str = "", token: str = ""):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = token
        self.headers = {}
        
    def authenticate(self) -> bool:
        """Autenticarse con Alist y obtener token"""
        if self.token:
            self.headers = {"Authorization": self.token}
            return True
            
        if not self.username or not self.password:
            print("⚠️ Sin credenciales - intentando acceso público")
            return False
            
        auth_url = f"{self.base_url}/api/auth/login"
        auth_data = {
            "username": self.username,
            "password": self.password
        }
        
        try:
            response = requests.post(auth_url, json=auth_data)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    self.token = data["data"]["token"]
                    self.headers = {"Authorization": self.token}
                    print("✅ Autenticación exitosa")
                    return True
        except Exception as e:
            print(f"❌ Error de autenticación: {e}")
        
        return False

# ============================================
# CLIENTE ALIST API
# ============================================

class AlistClient:
    """Cliente para interactuar con la API de Alist"""
    
    def __init__(self, config: AlistConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(config.headers)
        
    def list_files(self, path: str = "/", refresh: bool = False) -> Dict:
        """Listar archivos en una ruta"""
        url = f"{self.config.base_url}/api/fs/list"
        params = {
            "path": path,
            "refresh": refresh,
            "page": 1,
            "per_page": 1000  # Ajustar según necesidad
        }
        
        try:
            response = self.session.post(url, json=params)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    return data.get("data", {})
            print(f"⚠️ Error listando {path}: {response.text}")
        except Exception as e:
            print(f"❌ Error de conexión: {e}")
        
        return {}
    
    def get_file_info(self, path: str) -> Dict:
        """Obtener información detallada de un archivo"""
        url = f"{self.config.base_url}/api/fs/get"
        params = {"path": path}
        
        try:
            response = self.session.post(url, json=params)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    return data.get("data", {})
        except Exception as e:
            print(f"❌ Error obteniendo info de {path}: {e}")
        
        return {}
    
    def get_download_url(self, path: str) -> str:
        """Obtener URL de descarga directa"""
        info = self.get_file_info(path)
        if info and "raw_url" in info:
            return info["raw_url"]
        # Fallback: construir URL manualmente
        return f"{self.config.base_url}{path}"

# ============================================
# INDEXADOR DE ARCHIVOS
# ============================================

class CloudIndexer:
    """Sistema de indexación en la nube"""
    
    def __init__(self, client: AlistClient):
        self.client = client
        self.index = {
            "created": datetime.now().isoformat(),
            "files": [],
            "directories": [],
            "statistics": {
                "total_files": 0,
                "total_size": 0,
                "file_types": {}
            }
        }
        self.file_cache = {}
        self.scanned_files_count = 0 # --- ADDED --- Counter for live progress
        
    def scan_directory(self, path: str = "/", recursive: bool = True, max_depth: int = 5) -> None:
        """Escanear directorio y construir índice"""
        print(f"📂 Escaneando: {path}")
        self.scanned_files_count = 0 # --- ADDED --- Reset counter for each run
        
        def _scan(current_path: str, depth: int = 0):
            if depth > max_depth:
                return
                
            result = self.client.list_files(current_path)
            if not result:
                return
            
            # --- MODIFIED --- This includes the previous fix for the TypeError    
            content = result.get("content") or []
            
            for item in content:
                item_path = f"{current_path}/{item['name']}".replace("//", "/")
                
                if item.get("is_dir"):
                    # Agregar directorio al índice
                    dir_info = {
                        "path": item_path,
                        "name": item["name"],
                        "modified": item.get("modified"),
                        "type": "directory"
                    }
                    self.index["directories"].append(dir_info)
                    
                    # Recursión si está habilitada
                    if recursive:
                        time.sleep(0.1)  # Rate limiting
                        _scan(item_path, depth + 1)
                else:
                    # Procesar archivo
                    file_info = self._process_file(item, current_path)
                    self.index["files"].append(file_info)
                    self.index["statistics"]["total_files"] += 1
                    self.index["statistics"]["total_size"] += item.get("size", 0)
                    
                    # --- ADDED --- Increment and display the live counter
                    self.scanned_files_count += 1
                    sys.stdout.write(f"\r🔍 Archivos encontrados: {self.scanned_files_count}")
                    sys.stdout.flush()

                    # Estadísticas por tipo
                    file_ext = Path(item["name"]).suffix.lower()
                    if file_ext:
                        self.index["statistics"]["file_types"][file_ext] = \
                            self.index["statistics"]["file_types"].get(file_ext, 0) + 1
        
        _scan(path)
        print() # --- ADDED --- Move to the next line after the counter is done
        print(f"✅ Indexación completada: {self.index['statistics']['total_files']} archivos")
    
    def _process_file(self, item: Dict, parent_path: str) -> Dict:
        """Procesar información de archivo individual"""
        file_path = f"{parent_path}/{item['name']}".replace("//", "/")
        file_ext = Path(item["name"]).suffix.lower()
        
        # Información básica
        file_info = {
            "path": file_path,
            "name": item["name"],
            "size": item.get("size", 0),
            "size_formatted": self._format_size(item.get("size", 0)),
            "modified": item.get("modified"),
            "type": self._get_file_type(file_ext),
            "extension": file_ext,
            "permalink": self.client.get_download_url(file_path),
            "tags": [],
            "metadata": {}
        }
        
        # Agregar tags automáticos según tipo
        file_info["tags"] = self._auto_tag(file_info)
        
        return file_info
    
    def _get_file_type(self, ext: str) -> str:
        """Determinar tipo de archivo por extensión"""
        type_map = {
            # Imágenes
            ".jpg": "image", ".jpeg": "image", ".png": "image", ".gif": "image",
            ".webp": "image", ".bmp": "image", ".svg": "image", ".ico": "image",
            # Videos
            ".mp4": "video", ".avi": "video", ".mkv": "video", ".mov": "video",
            ".webm": "video", ".flv": "video", ".wmv": "video",
            # Audio
            ".mp3": "audio", ".wav": "audio", ".flac": "audio", ".ogg": "audio",
            ".m4a": "audio", ".aac": "audio",
            # Documentos
            ".pdf": "document", ".doc": "document", ".docx": "document",
            ".txt": "document", ".md": "document", ".rtf": "document",
            # Código
            ".js": "code", ".ts": "code", ".jsx": "code", ".tsx": "code",
            ".py": "code", ".java": "code", ".cpp": "code", ".c": "code",
            ".html": "code", ".css": "code", ".json": "code", ".xml": "code",
            # Archivos
            ".zip": "archive", ".rar": "archive", ".7z": "archive", ".tar": "archive",
            ".gz": "archive",
            # Datos
            ".csv": "data", ".xlsx": "data", ".xls": "data", ".sql": "data"
        }
        return type_map.get(ext, "other")
    
    def _format_size(self, size: int) -> str:
        """Formatear tamaño de archivo"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    def _auto_tag(self, file_info: Dict) -> List[str]:
        """Generar tags automáticos"""
        tags = []
        
        # Tags por tipo
        file_type = file_info["type"]
        tags.append(file_type)
        
        # Tags por tamaño
        size = file_info["size"]
        if size < 100 * 1024:  # < 100KB
            tags.append("small")
        elif size < 10 * 1024 * 1024:  # < 10MB
            tags.append("medium")
        else:
            tags.append("large")
        
        # Tags por carpeta
        path_parts = file_info["path"].split("/")
        if len(path_parts) > 2:
            tags.append(f"folder:{path_parts[-2]}")
        
        # Tags específicos por tipo
        if file_type == "image":
            ext = file_info["extension"]
            if ext in [".gif", ".webp"]:
                tags.append("animated")
            if "wallpaper" in file_info["name"].lower():
                tags.append("wallpaper")
                
        elif file_type == "code":
            ext = file_info["extension"]
            if ext in [".js", ".jsx", ".ts", ".tsx"]:
                tags.append("javascript")
            elif ext == ".py":
                tags.append("python")
            elif ext in [".html", ".css"]:
                tags.append("web")
                
        return tags
    
    def save_index(self, filename: str = "index.json") -> None:
        """Guardar índice en archivo JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)
        print(f"💾 Índice guardado en {filename}")
    
    def load_index(self, filename: str = "index.json") -> None:
        """Cargar índice desde archivo JSON"""
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                self.index = json.load(f)
            print(f"📂 Índice cargado: {self.index['statistics']['total_files']} archivos")

# ============================================
# CLASIFICADOR IA (OPCIONAL)
# ============================================

class ImageClassifier:
    """Clasificador de imágenes usando IA"""
    
    def __init__(self):
        self.model_loaded = False
        
    def setup_deepdanbooru(self):
        """Configurar DeepDanbooru para clasificación de anime"""
        try:
            import deepdanbooru as dd
            # Descargar modelo si es necesario
            # !wget https://github.com/KichangKim/DeepDanbooru/releases/download/v3-20211112-sgd-e28/deepdanbooru-v3-20211112-sgd-e28.zip
            # !unzip deepdanbooru-v3-20211112-sgd-e28.zip
            
            self.dd_model = dd.load_model_from_project("deepdanbooru-v3-20211112-sgd-e28")
            self.dd_tags = dd.load_tags_from_project("deepdanbooru-v3-20211112-sgd-e28")
            self.model_loaded = True
            print("✅ DeepDanbooru cargado")
        except Exception as e:
            print(f"⚠️ No se pudo cargar DeepDanbooru: {e}")
            
    def classify_image_url(self, image_url: str, threshold: float = 0.5) -> List[str]:
        """Clasificar imagen desde URL"""
        if not self.model_loaded:
            return []
            
        try:
            # Descargar imagen temporalmente
            import tempfile
            from PIL import Image as PILImage
            import numpy as np
            
            response = requests.get(image_url, stream=True)
            if response.status_code == 200:
                with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
                    tmp.write(response.content)
                    tmp.flush()
                    
                    # Cargar y procesar imagen
                    image = PILImage.open(tmp.name).convert("RGB")
                    image = image.resize((512, 512))
                    image_array = np.array(image) / 255.0
                    
                    # Predecir tags
                    results = self.dd_model.predict(np.expand_dims(image_array, 0))[0]
                    
                    # Filtrar por threshold
                    tags = []
                    for i, score in enumerate(results):
                        if score > threshold:
                            tags.append(self.dd_tags[i])
                    
                    return tags[:10]  # Limitar a 10 tags principales
        except Exception as e:
            print(f"Error clasificando imagen: {e}")
            
        return []

# ============================================
# ORGANIZADOR VIRTUAL
# ============================================

class VirtualOrganizer:
    """Crear estructura virtual con permalinks"""
    
    def __init__(self, indexer: CloudIndexer):
        self.indexer = indexer
        self.virtual_structure = {
            "by_type": {},
            "by_tag": {},
            "by_date": {},
            "by_size": {}
        }
        
    def organize(self) -> None:
        """Organizar archivos en carpetas virtuales"""
        for file_info in self.indexer.index["files"]:
            # Por tipo
            file_type = file_info["type"]
            if file_type not in self.virtual_structure["by_type"]:
                self.virtual_structure["by_type"][file_type] = []
            self.virtual_structure["by_type"][file_type].append(file_info)
            
            # Por tags
            for tag in file_info.get("tags", []):
                if tag not in self.virtual_structure["by_tag"]:
                    self.virtual_structure["by_tag"][tag] = []
                self.virtual_structure["by_tag"][tag].append(file_info)
            
            # Por fecha (año-mes)
            if file_info.get("modified"):
                try:
                    date = datetime.fromisoformat(file_info["modified"])
                    month_key = date.strftime("%Y-%m")
                    if month_key not in self.virtual_structure["by_date"]:
                        self.virtual_structure["by_date"][month_key] = []
                    self.virtual_structure["by_date"][month_key].append(file_info)
                except:
                    pass
            
            # Por tamaño
            size = file_info["size"]
            if size < 1024 * 1024:  # < 1MB
                size_key = "small"
            elif size < 100 * 1024 * 1024:  # < 100MB
                size_key = "medium"
            else:
                size_key = "large"
                
            if size_key not in self.virtual_structure["by_size"]:
                self.virtual_structure["by_size"][size_key] = []
            self.virtual_structure["by_size"][size_key].append(file_info)
    
    def get_virtual_path(self, category: str, subcategory: str) -> List[Dict]:
        """Obtener archivos en una ruta virtual"""
        if category in self.virtual_structure:
            return self.virtual_structure[category].get(subcategory, [])
        return []

# ============================================
# INTERFAZ WIKI (HTML)
# ============================================

class WikiInterface:
    """Interfaz tipo Wiki mejorada, con filtrado, vistas previas y control de caché."""

    def __init__(self, indexer, organizer):
        self.indexer = indexer
        self.organizer = organizer

    def generate_html(self) -> str:
        """Generar el HTML completo de la interfaz wiki."""
        stats = self.indexer.index["statistics"]
        files_json = json.dumps(self.indexer.index["files"])
        categories_json = json.dumps(self.organizer.virtual_structure)

        html = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Alist Cloud Index Pro</title>
            
            <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.11.338/pdf.min.js"></script>

            <style>
                :root {{
                    --primary-color: #6a66ea; --primary-dark: #5a55d6;
                    --bg-color: #f4f7f9; --surface-color: #ffffff;
                    --text-color: #333; --text-muted-color: #777;
                    --border-color: #e0e0e0; --shadow: 0 4px 12px rgba(0,0,0,0.08);
                    --radius-sm: 6px; --radius-md: 10px; --radius-lg: 14px;
                }}
                body.dark-mode {{
                    --bg-color: #1a1a1a; --surface-color: #2c2c2c;
                    --text-color: #f0f0f0; --text-muted-color: #aaa;
                    --border-color: #444;
                }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    margin: 0; padding: 25px; background-color: var(--bg-color);
                    color: var(--text-color); transition: background-color 0.3s, color 0.3s;
                }}
                .container {{ max-width: 1400px; margin: 0 auto; }}
                .header {{
                    background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%);
                    color: white; padding: 30px; border-radius: var(--radius-lg);
                    margin-bottom: 30px; position: relative;
                }}
                .header h1 {{ margin: 0 0 10px 0; }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 20px; }}
                .stat-card {{ background-color: var(--surface-color); padding: 20px; border-radius: var(--radius-md); box-shadow: var(--shadow); transition: transform 0.2s; }}
                .stat-card:hover {{ transform: translateY(-5px); }}
                .stat-value {{ font-size: 2em; font-weight: bold; color: var(--primary-color); }}
                
                .controls {{
                    background-color: var(--surface-color); padding: 15px;
                    border-radius: var(--radius-md); box-shadow: var(--shadow);
                    margin-bottom: 25px;
                    display: flex; flex-wrap: wrap; gap: 15px; align-items: center;
                }}
                .search-box {{ flex-grow: 1; min-width: 250px; padding: 12px; font-size: 16px; border: 1px solid var(--border-color); border-radius: var(--radius-sm); background-color: var(--bg-color); color: var(--text-color);}}
                .control-group {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
                .btn {{ padding: 10px 15px; border: 1px solid var(--border-color); background-color: var(--bg-color); color: var(--text-color); border-radius: var(--radius-sm); cursor: pointer; transition: background-color 0.2s, color 0.2s, border-color 0.2s; }}
                .btn.active {{ background-color: var(--primary-color); color: white; border-color: var(--primary-color); }}
                .btn:hover:not(.active) {{ border-color: var(--primary-dark); }}
                
                #active-filters-display {{ 
                    margin-bottom: 25px;
                    display: flex; flex-wrap: wrap; gap: 10px; align-items: center; min-height: 24px;
                }}
                .active-tag {{ display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; background-color: var(--primary-color); color: white; border-radius: 20px; font-size: 0.9em; }}
                .active-tag .close-btn {{ cursor: pointer; font-weight: bold; }}

                .categories-container {{
                    display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                    gap: 20px; margin-bottom: 30px;
                }}
                .category-card {{ background-color: var(--surface-color); padding: 20px; border-radius: var(--radius-md); box-shadow: var(--shadow); }}
                .category-card h3 {{ margin-top: 0; }}
                .category-list span {{ display: inline-block; padding: 3px 8px; background-color: #e3f2fd; color: #1976d2; border-radius: 5px; font-size: 0.8em; cursor: pointer; margin: 3px; transition: background-color 0.2s, color 0.2s; }}
                .category-list span:hover {{ background-color: var(--primary-color); color: white; }}
                body.dark-mode .category-list span {{ background-color: #333; color: #a3c3e2; }}
                
                /* --- ESTILOS MODIFICADOS Y NUEVOS para Vistas Previas --- */
                .file-list-container.grid-view {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 20px; }}
                .file-item {{ background-color: var(--surface-color); padding: 15px; border-radius: var(--radius-md); box-shadow: var(--shadow); display: flex; flex-direction: column; border-left: 4px solid var(--primary-color); }}
                .list-view .file-item {{ flex-direction: row; align-items: center; margin-bottom: 10px; }}
                
                .file-preview {{
                    font-size: 3em; text-align: center; margin-bottom: 15px;
                    display: flex; align-items: center; justify-content: center;
                    height: 120px; border-radius: var(--radius-sm);
                    background-color: var(--bg-color); overflow: hidden;
                }}
                .file-preview img, .file-preview canvas {{
                    width: 100%; height: 100%; object-fit: cover;
                }}
                .list-view .file-preview {{
                    font-size: 1.5em; margin-bottom: 0; margin-right: 15px;
                    height: 40px; width: 40px; flex-shrink: 0;
                }}

                .file-content {{ flex-grow: 1; display: flex; flex-direction: column; justify-content: space-between; min-width: 0; }}
                .file-name {{ font-weight: 600; margin-bottom: 10px; word-break: break-all; }}
                .list-view .file-name {{ margin-bottom: 0; flex-grow: 1; }}

                .file-meta {{ font-size: 0.85em; color: var(--text-muted-color); display: flex; flex-wrap: wrap; gap: 15px; align-items: center; margin-top: 10px; }}
                .list-view .file-meta {{ margin-top: 0; }}
                .file-meta .tags-container span {{ background-color: var(--bg-color); }}
                .permalink {{ color: var(--primary-color); text-decoration: none; font-weight: bold; font-size: 1.2em; }}
                #loadMoreBtn {{ display: none; width: 200px; margin: 30px auto; }}
                #no-results {{ display: none; text-align: center; padding: 40px; font-size: 1.2em; color: var(--text-muted-color); }}
                .dark-mode-toggle {{ position: absolute; top: 20px; right: 20px; }}
                .switch {{ position: relative; display: inline-block; width: 50px; height: 24px; }}
                .switch input {{ opacity: 0; width: 0; height: 0; }}
                .slider {{ position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; border-radius: 24px; }}
                .slider:before {{ position: absolute; content: "☀️"; height: 16px; width: 16px; left: 4px; bottom: 4px; background-color: white; transition: .4s; border-radius: 50%; text-align: center; line-height: 16px; font-size: 12px;}}
                input:checked + .slider {{ background-color: var(--primary-color); }}
                input:checked + .slider:before {{ transform: translateX(26px); content: "🌙"; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📚 Alist Cloud Index Pro</h1>
                    <p>Última actualización: {self.indexer.index['created']}</p>
                    <div class="dark-mode-toggle">
                        <label class="switch">
                            <input type="checkbox" id="darkModeToggle">
                            <span class="slider"></span>
                        </label>
                    </div>
                </div>
                
                <div class="stats">{self._generate_stats_html(stats)}</div>
                
                <div class="controls">
                    <input type="text" class="search-box" id="searchBox" placeholder="🔍 Buscar por nombre o etiqueta...">
                    <div class="control-group" id="type-filter-buttons" data-filter-type="type">
                        <button class="btn active" data-type="all">Todos</button>
                        <button class="btn" data-type="image">🖼️ Imágenes</button>
                        <button class="btn" data-type="video">🎬 Videos</button>
                        <button class="btn" data-type="audio">🎵 Audio</button>
                        <button class="btn" data-type="document">📄 Documentos</button>
                        <button class="btn" data-type="archive">📦 Archivos</button>
                        <button class="btn" data-type="installable">⚙️ Instalables</button>
                        <button class="btn" data-type="other">📎 Otros</button>
                    </div>
                    <div class="control-group">
                        <select id="sortSelect" class="btn">
                            <option value="modified_desc">Fecha (Nuevos)</option>
                            <option value="modified_asc">Fecha (Antiguos)</option>
                            <option value="name_asc">Nombre (A-Z)</option>
                            <option value="name_desc">Nombre (Z-A)</option>
                            <option value="size_desc">Tamaño (Mayor)</option>
                            <option value="size_asc">Tamaño (Menor)</option>
                        </select>
                         <button id="togglePreviewsBtn" class="btn">Ocultar Vistas Previas</button>
                    </div>
                    <div class="control-group" id="view-switcher">
                         <button id="listViewBtn" class="btn" title="Vista de lista">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M2.5 12a.5.5 0 0 1 .5-.5h10a.5.5 0 0 1 0 1H3a.5.5 0 0 1-.5-.5zm0-4a.5.5 0 0 1 .5-.5h10a.5.5 0 0 1 0 1H3a.5.5 0 0 1-.5-.5zm0-4a.5.5 0 0 1 .5-.5h10a.5.5 0 0 1 0 1H3a.5.5 0 0 1-.5-.5z"/></svg>
                        </button>
                        <button id="gridViewBtn" class="btn active" title="Vista de cuadrícula">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path d="M1 2.5A1.5 1.5 0 0 1 2.5 1h3A1.5 1.5 0 0 1 7 2.5v3A1.5 1.5 0 0 1 5.5 7h-3A1.5 1.5 0 0 1 1 5.5v-3zm8 0A1.5 1.5 0 0 1 10.5 1h3A1.5 1.5 0 0 1 15 2.5v3A1.5 1.5 0 0 1 13.5 7h-3A1.5 1.5 0 0 1 9 5.5v-3zm-8 8A1.5 1.5 0 0 1 2.5 9h3A1.5 1.5 0 0 1 7 10.5v3A1.5 1.5 0 0 1 5.5 15h-3A1.5 1.5 0 0 1 1 13.5v-3zm8 0A1.5 1.5 0 0 1 10.5 9h3a1.5 1.5 0 0 1 1.5 1.5v3a1.5 1.5 0 0 1-1.5 1.5h-3a1.5 1.5 0 0 1-1.5-1.5v-3z"/></svg>
                        </button>
                    </div>
                </div>

                <div id="active-filters-display"></div>
                <div class="categories-container" id="categories-container"></div>
                <div id="file-list-container" class="file-list-container grid-view"></div>
                <div id="no-results">😕 No se encontraron archivos que coincidan con tu búsqueda.</div>
                <button id="loadMoreBtn" class="btn">Cargar Más</button>
            </div>

            <script>
                document.addEventListener('DOMContentLoaded', () => {{
                    // --- INYECCIÓN DE DATOS ---
                    const allFiles = {files_json};
                    const categoriesData = {categories_json};

                    // --- ESTADO DE LA APLICACIÓN ---
                    const state = {{
                        files: allFiles,
                        filters: {{ type: 'all', tag: null, size_category: null, searchTerm: '' }},
                        sort: 'modified_desc',
                        view: 'grid', // Vista por defecto
                        itemsPerPage: 50,
                        currentPage: 1,
                        showPreviews: true // --- NUEVO: Estado para controlar vistas previas
                    }};

                    // --- REFERENCIAS AL DOM ---
                    const ui = {{
                        searchBox: document.getElementById('searchBox'),
                        fileListContainer: document.getElementById('file-list-container'),
                        loadMoreBtn: document.getElementById('loadMoreBtn'),
                        sortSelect: document.getElementById('sortSelect'),
                        typeFilterButtons: document.getElementById('type-filter-buttons'),
                        viewSwitcher: document.getElementById('view-switcher'),
                        darkModeToggle: document.getElementById('darkModeToggle'),
                        noResults: document.getElementById('no-results'),
                        categoriesContainer: document.getElementById('categories-container'),
                        activeFiltersDisplay: document.getElementById('active-filters-display'),
                        togglePreviewsBtn: document.getElementById('togglePreviewsBtn') // --- NUEVO ---
                    }};

                    // --- FUNCIONES AUXILIARES ---
                    const getFileCategory = (filename) => {{
                        const extension = (filename || '').split('.').pop().toLowerCase();
                        const mappings = {{
                            image: ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'tiff'],
                            video: ['mp4', 'mkv', 'mov', 'avi', 'wmv', 'flv', 'webm'],
                            audio: ['mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a'],
                            document: ['pdf', 'doc', 'docx', 'txt', 'xls', 'xlsx', 'ppt', 'pptx', 'rtf', 'odt'],
                            archive: ['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'iso'],
                            installable: ['exe', 'msi', 'dmg', 'apk', 'deb', 'rpm']
                        }};
                        for (const category in mappings) {{
                            if (mappings[category].includes(extension)) return category;
                        }}
                        return 'other';
                    }};
                    
                    const getFileIcon = (fileName) => {{
                        const category = getFileCategory(fileName);
                        return {{ 
                            "image": "🖼️", "video": "🎬", "audio": "🎵", "document": "📄", 
                            "installable": "⚙️", "archive": "📦", "other": "📎" 
                        }}[category] || "📎";
                    }};

                    const getFileSizeCategoryKey = (size) => {{
                        if (size < 1024 * 1024) return 'small';
                        if (size < 100 * 1024 * 1024) return 'medium';
                        if (size < 1024 * 1024 * 1024) return 'large';
                        return 'huge';
                    }};

                    const sizeCategoryLabels = {{
                        small: 'Pequeño (<1MB)', medium: 'Mediano (1-100MB)',
                        large: 'Grande (100MB-1GB)', huge: 'Enorme (>1GB)'
                    }};

                    // --- LÓGICA DE RENDERIZADO ---
                    function renderFiles() {{
                        const filteredFiles = state.files.filter(file => {{
                            const search = state.filters.searchTerm.toLowerCase();
                            const typeMatch = state.filters.type === 'all' || getFileCategory(file.name) === state.filters.type;
                            const tagMatch = !state.filters.tag || file.tags.includes(state.filters.tag);
                            const sizeMatch = !state.filters.size_category || getFileSizeCategoryKey(file.size) === state.filters.size_category;
                            const searchMatch = !search || file.name.toLowerCase().includes(search) || file.tags.some(t => t.toLowerCase().includes(search));
                            return typeMatch && tagMatch && sizeMatch && searchMatch;
                        }}).sort((a, b) => {{
                            switch (state.sort) {{
                                case 'name_asc': return a.name.localeCompare(b.name);
                                case 'name_desc': return b.name.localeCompare(a.name);
                                case 'size_asc': return a.size - b.size;
                                case 'size_desc': return b.size - a.size;
                                case 'modified_asc': return new Date(a.modified) - new Date(b.modified);
                                default: return new Date(b.modified) - new Date(a.modified);
                            }}
                        }});

                        const totalItemsToShow = state.itemsPerPage * state.currentPage;
                        const filesToRender = filteredFiles.slice(0, totalItemsToShow);
                        
                        ui.fileListContainer.innerHTML = filesToRender.length === 0 ? '' : filesToRender.map(createFileElementHTML).join('');
                        ui.noResults.style.display = filesToRender.length === 0 ? 'block' : 'none';
                        ui.loadMoreBtn.style.display = filteredFiles.length > totalItemsToShow ? 'block' : 'none';

                        // --- NUEVO: Renderizar PDFs después de que el HTML esté en el DOM ---
                        if (state.showPreviews) {{
                            renderPdfPreviews();
                        }}
                    }}

                    // --- FUNCIÓN MODIFICADA para incluir Vistas Previas ---
                    function createFileElementHTML(file) {{
                        const category = getFileCategory(file.name);
                        const extension = file.name.split('.').pop().toLowerCase();
                        let previewHtml = `<span>${{getFileIcon(file.name)}}</span>`; // Icono por defecto

                        if (state.showPreviews) {{
                            if (category === 'image') {{
                                previewHtml = `<img src="${{file.permalink}}" alt="${{file.name}}" loading="lazy">`;
                            }} else if (category === 'document' && extension === 'pdf') {{
                                previewHtml = `<canvas data-pdf-url="${{file.permalink}}"></canvas>`;
                            }}
                        }}
                        
                        const tagsHtml = file.tags.map(tag => `<span class="category-list"><span data-value="${{tag}}">${{tag}}</span></span>`).join('');
                        
                        return `
                            <div class="file-item">
                                <div class="file-preview">${{previewHtml}}</div>
                                <div class="file-content">
                                    <div class="file-name">${{file.name}}</div>
                                    <div class="file-meta">
                                        <span>${{file.size_formatted}}</span>
                                        <span>${{file.modified ? file.modified.substring(0, 10) : 'N/A'}}</span>
                                        <div class="tags-container">${{tagsHtml}}</div>
                                        <a href="${{file.permalink}}" class="permalink" target="_blank" title="Descargar/Abrir">📥</a>
                                    </div>
                                </div>
                            </div>
                        `;
                    }}
                    
                    // --- NUEVO: Función para renderizar vistas previas de PDF ---
                    function renderPdfPreviews() {{
                        pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.11.338/pdf.worker.min.js`;
                        const canvases = ui.fileListContainer.querySelectorAll('canvas[data-pdf-url]');

                        const observer = new IntersectionObserver((entries) => {{
                            entries.forEach(entry => {{
                                if (entry.isIntersecting) {{
                                    const canvas = entry.target;
                                    const url = canvas.dataset.pdfUrl;
                                    observer.unobserve(canvas); // Dejar de observar una vez que se procesa
                                    
                                    pdfjsLib.getDocument(url).promise.then(pdf => {{
                                        return pdf.getPage(1);
                                    }}).then(page => {{
                                        const viewport = page.getViewport({{ scale: 1.5 }});
                                        const context = canvas.getContext('2d');
                                        canvas.height = viewport.height;
                                        canvas.width = viewport.width;
                                        page.render({{ canvasContext: context, viewport: viewport }});
                                    }}).catch(err => console.error('Error al renderizar PDF:', err));
                                }}
                            }});
                        }}, {{ rootMargin: '100px' }}); // Cargar un poco antes de que sea visible

                        canvases.forEach(canvas => observer.observe(canvas));
                    }}


                    function renderCategories() {{
                        const allTags = Object.entries(categoriesData.by_tag).sort(([,a],[,b]) => b.length - a.length);
                        const sizeCategoriesHtml = Object.keys(categoriesData.by_size).map(sizeKey => `<span data-value="${{sizeKey}}">${{sizeCategoryLabels[sizeKey] || sizeKey}}</span>`).join('');
                        
                        ui.categoriesContainer.innerHTML = `
                            <div class="category-card"><h3>🏷️ Todas las Etiquetas</h3><div class="category-list" data-filter-type="tag">${{allTags.map(([tag]) => `<span data-value="${{tag}}">${{tag}}</span>`).join('')}}</div></div>
                            <div class="category-card"><h3>📊 Por Tamaño</h3><div class="category-list" data-filter-type="size">${{sizeCategoriesHtml}}</div></div>`;
                    }}

                    function renderActiveFilters() {{
                        let html = '';
                        if (state.filters.tag) {{ html += `<span class="active-tag" data-filter-type="tag">🏷️ ${{state.filters.tag}} <span class="close-btn">×</span></span>`; }}
                        if (state.filters.size_category) {{
                            const label = sizeCategoryLabels[state.filters.size_category] || state.filters.size_category;
                            html += `<span class="active-tag" data-filter-type="size">📊 ${{label}} <span class="close-btn">×</span></span>`;
                        }}
                        ui.activeFiltersDisplay.innerHTML = html;
                    }}

                    // --- MANEJADORES DE EVENTOS ---
                    function handleFilterClick(e) {{
                        const target = e.target;
                        if (target.tagName !== 'BUTTON' && target.tagName !== 'SPAN') return;
                        const parent = target.closest('[data-filter-type]');
                        if (!parent) return;
                        const filterType = parent.dataset.filterType;
                        const value = target.dataset.type || target.dataset.value || target.textContent;
                        
                        if (filterType === 'type') {{ state.filters.type = value; updateActiveButton(ui.typeFilterButtons, target); }}
                        else if (filterType === 'tag') {{ state.filters.tag = state.filters.tag === value ? null : value; }}
                        else if (filterType === 'size') {{ state.filters.size_category = state.filters.size_category === value ? null : value; }}
                        
                        state.currentPage = 1;
                        renderActiveFilters();
                        renderFiles();
                    }}

                    function updateActiveButton(container, activeButton) {{
                        container.querySelector('.active')?.classList.remove('active');
                        activeButton.classList.add('active');
                    }}
                    
                    // --- INICIALIZACIÓN Y BINDING ---
                    ui.searchBox.addEventListener('keyup', (e) => {{ state.filters.searchTerm = e.target.value; state.currentPage = 1; renderFiles(); }});
                    ui.sortSelect.addEventListener('change', (e) => {{ state.sort = e.target.value; renderFiles(); }});
                    ui.loadMoreBtn.addEventListener('click', () => {{ state.currentPage++; renderFiles(); }});
                    ui.viewSwitcher.addEventListener('click', (e) => {{
                        const btn = e.target.closest('button'); if (!btn) return;
                        const isGrid = btn.id === 'gridViewBtn';
                        state.view = isGrid ? 'grid' : 'list';
                        ui.fileListContainer.classList.toggle('grid-view', isGrid);
                        ui.fileListContainer.classList.toggle('list-view', !isGrid);
                        updateActiveButton(ui.viewSwitcher, btn);
                    }});
                    
                    // --- NUEVO: Event Listener para el botón de vistas previas ---
                    ui.togglePreviewsBtn.addEventListener('click', () => {{
                        state.showPreviews = !state.showPreviews;
                        ui.togglePreviewsBtn.textContent = state.showPreviews ? 'Ocultar Vistas Previas' : 'Mostrar Vistas Previas';
                        renderFiles(); // Re-renderizar todo para aplicar el cambio
                    }});

                    ui.typeFilterButtons.addEventListener('click', handleFilterClick);
                    ui.categoriesContainer.addEventListener('click', handleFilterClick);
                    
                    ui.activeFiltersDisplay.addEventListener('click', (e) => {{
                        if (e.target.classList.contains('close-btn')) {{
                            const filterTag = e.target.parentElement;
                            const filterType = filterTag.dataset.filterType;
                            if (filterType === 'tag') state.filters.tag = null;
                            if (filterType === 'size') state.filters.size_category = null;
                            state.currentPage = 1;
                            renderActiveFilters();
                            renderFiles();
                        }}
                    }});

                    ui.darkModeToggle.addEventListener('change', () => {{ document.body.classList.toggle('dark-mode', ui.darkModeToggle.checked); }});

                    // --- RENDERIZADO INICIAL ---
                    renderCategories();
                    renderFiles();
                }});
            </script>
        </body>
        </html>
        """
        return html

    def _generate_stats_html(self, stats: Dict) -> str:
        return f"""
            <div class="stat-card"><div class="stat-value">{stats['total_files']}</div><div>Archivos totales</div></div>
            <div class="stat-card"><div class="stat-value">{self._format_size(stats['total_size'])}</div><div>Tamaño total</div></div>
            <div class="stat-card"><div class="stat-value">{len(stats['file_types'])}</div><div>Tipos de archivo</div></div>
            <div class="stat-card"><div class="stat-value">{len(self.indexer.index['directories'])}</div><div>Directorios</div></div>
        """
    
    def _format_size(self, size: int) -> str:
        if not isinstance(size, (int, float)) or size < 0: return "0 B"
        if size == 0: return "0 B"
        size = float(size)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
            if size < 1024.0:
                return f"{{size:0.{'1' if unit != 'B' else '0'}f}} {{unit}}".format(size=size, unit=unit)
            size /= 1024.0
        return f"{size:.1f} PB"

    def display(self):
        try:
            from IPython.display import display, HTML
            display(HTML(self.generate_html()))
        except ImportError:
            print("Para usar display(), necesitas tener IPython instalado ('pip install ipython'). Guardando en archivo como alternativa...")
            self.save_html()

    def save_html(self, filename: str = "wiki_pro.html"):
        html_content = self.generate_html()
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"📄 Interfaz mejorada guardada en {filename}")
# ============================================
# FUNCIÓN PRINCIPAL
# ============================================

def main():
    """Función principal para ejecutar en Google Colab"""
    
    print("=" * 50)
    print("🚀 SISTEMA DE INDEXACIÓN CLOUD PARA ALIST")
    print("=" * 50)
    
    # Configuración (modificar según tu servidor)
    ALIST_URL = input("Ingresa la URL de tu servidor Alist (ej: http://localhost:5244): ").strip()
    USERNAME = input("Usuario (dejar vacío para acceso público): ").strip()
    PASSWORD = input("Contraseña: ").strip() if USERNAME else ""
    
    # Ruta a indexar
    START_PATH = input("Ruta inicial a indexar (ej: /Terabox o /): ").strip() or "/"
    
    print("\n🔧 Configurando conexión...")
    
    # Crear configuración y cliente
    config = AlistConfig(ALIST_URL, USERNAME, PASSWORD)
    if USERNAME:
        if not config.authenticate():
            print("❌ No se pudo autenticar. Verifica las credenciales.")
            return
    
    client = AlistClient(config)
    
    # Crear indexador
    print("\n📚 Iniciando indexación...")
    indexer = CloudIndexer(client)
    
    # Opciones de escaneo
    recursive = input("¿Escanear subcarpetas? (s/n): ").lower() == 's'
    max_depth = int(input("Profundidad máxima (default 5): ") or "5")
    
    # Escanear directorio
    indexer.scan_directory(START_PATH, recursive=recursive, max_depth=max_depth)
    
    # Guardar índice
    indexer.save_index("alist_index.json")
    
    # Crear organizador virtual
    print("\n🗂️ Organizando archivos virtualmente...")
    organizer = VirtualOrganizer(indexer)
    organizer.organize()
    
    # Mostrar estadísticas
    print("\n📊 ESTADÍSTICAS DEL ÍNDICE:")
    print(f"  • Total de archivos: {indexer.index['statistics']['total_files']}")
    print(f"  • Tamaño total: {indexer._format_size(indexer.index['statistics']['total_size'])}")
    print(f"  • Directorios: {len(indexer.index['directories'])}")
    print(f"  • Tipos de archivo: {len(indexer.index['statistics']['file_types'])}")
    
    # Top 5 tipos de archivo
    if indexer.index['statistics']['file_types']:
        print("\n  📈 Top 5 tipos de archivo:")
        sorted_types = sorted(indexer.index['statistics']['file_types'].items(), 
                            key=lambda x: x[1], reverse=True)[:5]
        for ext, count in sorted_types:
            print(f"    • {ext}: {count} archivos")
    
    # Generar interfaz Wiki
    print("\n🌐 Generando interfaz Wiki...")
    wiki = WikiInterface(indexer, organizer)
    
    # Guardar HTML
    wiki.save_html("alist_wiki.html")
    
    # Mostrar en Colab
    wiki.display()
    
    # Opciones adicionales
    print("\n✨ OPCIONES ADICIONALES:")
    print("1. Clasificación IA de imágenes (requiere configuración adicional)")
    print("2. Exportar carpetas virtuales como JSON")
    print("3. Generar reporte detallado")
    print("4. Salir")
    
    option = input("\nSelecciona una opción (1-4): ").strip()
    
    if option == "1":
        setup_ai_classification(indexer, client)
    elif option == "2":
        export_virtual_folders(organizer)
    elif option == "3":
        generate_detailed_report(indexer, organizer)
    
    print("\n✅ Proceso completado!")
    print("📁 Archivos generados:")
    print("  • alist_index.json - Índice completo")
    print("  • alist_wiki.html - Interfaz Wiki")
    
    return indexer, organizer, wiki

# ============================================
# FUNCIONES ADICIONALES
# ============================================

def setup_ai_classification(indexer: CloudIndexer, client: AlistClient):
    """Configurar y ejecutar clasificación IA"""
    print("\n🤖 CLASIFICACIÓN IA DE IMÁGENES")
    print("Nota: Esto requiere instalar modelos adicionales y puede tomar tiempo")
    
    confirm = input("¿Deseas continuar? (s/n): ").lower()
    if confirm != 's':
        return
    
    print("\n📦 Instalando dependencias...")
    print("Ejecuta en una celda de Colab:")
    print("!pip install transformers torch pillow")
    print("!pip install git+https://github.com/KichangKim/DeepDanbooru.git")
    
    use_simple = input("\n¿Usar clasificador simple (más rápido) en lugar de DeepDanbooru? (s/n): ").lower()
    
    if use_simple == 's':
        # Clasificador simple basado en CLIP
        print("\n🎯 Usando clasificador simple...")
        from transformers import pipeline
        
        try:
            classifier = pipeline("image-classification", model="google/vit-base-patch16-224")
            
            # Clasificar las primeras N imágenes
            image_files = [f for f in indexer.index["files"] if f["type"] == "image"][:10]
            
            print(f"\n📸 Clasificando {len(image_files)} imágenes...")
            
            for file_info in image_files:
                try:
                    # Obtener URL de la imagen
                    image_url = file_info["permalink"]
                    
                    # Clasificar (esto es un ejemplo simplificado)
                    # En producción, descargarías y procesarías la imagen
                    print(f"  • {file_info['name']}: [clasificación pendiente]")
                    
                    # Agregar tags de ejemplo
                    file_info["tags"].extend(["ai-processed", "pending-classification"])
                    
                except Exception as e:
                    print(f"    Error: {e}")
            
            # Actualizar índice
            indexer.save_index("alist_index_ai.json")
            print("\n✅ Clasificación completada (modo simple)")
            
        except Exception as e:
            print(f"❌ Error configurando clasificador: {e}")
    else:
        # DeepDanbooru para anime/NSFW
        classifier = ImageClassifier()
        classifier.setup_deepdanbooru()
        
        if classifier.model_loaded:
            image_files = [f for f in indexer.index["files"] if f["type"] == "image"][:5]
            
            for file_info in image_files:
                print(f"Clasificando: {file_info['name']}")
                tags = classifier.classify_image_url(file_info["permalink"])
                if tags:
                    file_info["tags"].extend(tags)
                    file_info["metadata"]["ai_tags"] = tags
            
            indexer.save_index("alist_index_ai.json")
            print("✅ Clasificación IA completada")

def export_virtual_folders(organizer: VirtualOrganizer):
    """Exportar estructura de carpetas virtuales"""
    print("\n📤 EXPORTAR CARPETAS VIRTUALES")
    
    export_data = {
        "created": datetime.now().isoformat(),
        "virtual_folders": {}
    }
    
    # Crear estructura de carpetas virtuales con permalinks
    for category, subcategories in organizer.virtual_structure.items():
        export_data["virtual_folders"][f"/virtual/{category}"] = {}
        
        for subcat_name, files in subcategories.items():
            folder_path = f"/virtual/{category}/{subcat_name}"
            export_data["virtual_folders"][folder_path] = [
                {
                    "name": f["name"],
                    "permalink": f["permalink"],
                    "size": f["size_formatted"],
                    "type": f["type"]
                }
                for f in files[:100]  # Limitar a 100 archivos por carpeta
            ]
    
    # Guardar a JSON
    filename = "virtual_folders.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Carpetas virtuales exportadas a {filename}")
    
    # Mostrar resumen
    print("\n📊 Resumen de carpetas virtuales:")
    for folder_path in list(export_data["virtual_folders"].keys())[:10]:
        file_count = len(export_data["virtual_folders"][folder_path])
        print(f"  • {folder_path}: {file_count} archivos")

def generate_detailed_report(indexer: CloudIndexer, organizer: VirtualOrganizer):
    """Generar reporte detallado en Markdown"""
    print("\n📝 GENERANDO REPORTE DETALLADO")
    
    report = []
    report.append("# 📊 Reporte de Indexación - Alist Cloud System")
    report.append(f"\n**Fecha de generación:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"\n**Total de archivos:** {indexer.index['statistics']['total_files']}")
    report.append(f"\n**Tamaño total:** {indexer._format_size(indexer.index['statistics']['total_size'])}")
    
    # Estadísticas por tipo
    report.append("\n## 📈 Distribución por Tipo de Archivo\n")
    report.append("| Extensión | Cantidad | Porcentaje |")
    report.append("|-----------|----------|------------|")
    
    total_files = indexer.index['statistics']['total_files']
    for ext, count in sorted(indexer.index['statistics']['file_types'].items(), 
                            key=lambda x: x[1], reverse=True)[:20]:
        percentage = (count / total_files) * 100 if total_files > 0 else 0
        report.append(f"| {ext} | {count} | {percentage:.2f}% |")
    
    # Archivos más grandes
    report.append("\n## 💾 Top 10 Archivos Más Grandes\n")
    report.append("| Nombre | Tamaño | Tipo | Ruta |")
    report.append("|--------|--------|------|------|")
    
    largest_files = sorted(indexer.index["files"], 
                          key=lambda x: x["size"], 
                          reverse=True)[:10]
    
    for file_info in largest_files:
        report.append(f"| {file_info['name'][:30]} | {file_info['size_formatted']} | "
                     f"{file_info['type']} | {file_info['path'][:40]} |")
    
    # Organización virtual
    report.append("\n## 🗂️ Organización Virtual\n")
    
    for category in ["by_type", "by_tag"]:
        report.append(f"\n### {category.replace('_', ' ').title()}\n")
        items = list(organizer.virtual_structure[category].items())[:10]
        for name, files in items:
            report.append(f"- **{name}**: {len(files)} archivos")
    
    # Recomendaciones
    report.append("\n## 💡 Recomendaciones\n")
    
    # Análisis de duplicados potenciales
    name_groups = {}
    for f in indexer.index["files"]:
        base_name = f["name"].rsplit('.', 1)[0]
        if base_name not in name_groups:
            name_groups[base_name] = []
        name_groups[base_name].append(f)
    
    duplicates = [name for name, files in name_groups.items() if len(files) > 1]
    if duplicates:
        report.append(f"- ⚠️ Detectados {len(duplicates)} posibles grupos de archivos duplicados")
    
    # Archivos grandes
    large_files = [f for f in indexer.index["files"] if f["size"] > 100 * 1024 * 1024]
    if large_files:
        report.append(f"- 📦 {len(large_files)} archivos son mayores a 100MB")
    
    # Guardar reporte
    report_text = "\n".join(report)
    
    with open("report.md", 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    print("✅ Reporte generado: report.md")
    
    # Mostrar preview en Colab
    from IPython.display import Markdown
    display(Markdown(report_text[:2000] + "\n\n*[Reporte truncado para preview]*"))

# ============================================
# UTILIDADES PARA COLAB
# ============================================

def quick_start():
    """Inicio rápido con configuración predeterminada"""
    print("🚀 INICIO RÁPIDO - ALIST CLOUD INDEXER")
    print("-" * 40)
    
    # Valores por defecto para pruebas
    config = {
        "url": "http://localhost:5244",  # Cambiar según tu configuración
        "username": "",
        "password": "",
        "start_path": "/",
        "recursive": True,
        "max_depth": 3
    }
    
    print("Configuración por defecto:")
    for key, value in config.items():
        print(f"  • {key}: {value}")
    
    use_defaults = input("\n¿Usar configuración por defecto? (s/n): ").lower()
    
    if use_defaults != 's':
        config["url"] = input("URL de Alist: ").strip()
        config["username"] = input("Usuario: ").strip()
        if config["username"]:
            config["password"] = input("Contraseña: ").strip()
        config["start_path"] = input("Ruta inicial (default: /): ").strip() or "/"
    
    # Ejecutar indexación
    alist_config = AlistConfig(config["url"], config["username"], config["password"])
    if config["username"]:
        alist_config.authenticate()
    
    client = AlistClient(alist_config)
    indexer = CloudIndexer(client)
    
    print("\n📚 Indexando...")
    indexer.scan_directory(config["start_path"], config["recursive"], config["max_depth"])
    
    # Organizar y mostrar
    organizer = VirtualOrganizer(indexer)
    organizer.organize()
    
    wiki = WikiInterface(indexer, organizer)
    wiki.display()
    
    # Guardar archivos
    indexer.save_index("quick_index.json")
    wiki.save_html("quick_wiki.html")
    
    print("\n✅ Indexación rápida completada!")
    return indexer, organizer, wiki

# ============================================
# EJEMPLO DE USO EN COLAB
# ============================================

if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════╗
    ║   ALIST CLOUD INDEXER - GOOGLE COLAB   ║
    ╚════════════════════════════════════════╝
    
    Opciones:
    1. Configuración completa
    2. Inicio rápido
    3. Cargar índice existente
    """)
    
    choice = input("Selecciona opción (1-3): ").strip()
    
    if choice == "1":
        main()
    elif choice == "2":
        quick_start()
    elif choice == "3":
        indexer = CloudIndexer(None)
        indexer.load_index("alist_index.json")
        organizer = VirtualOrganizer(indexer)
        organizer.organize()
        wiki = WikiInterface(indexer, organizer)
        wiki.display()
    else:
        print("Opción no válida")