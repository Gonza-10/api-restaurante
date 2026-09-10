#============================================================================== 
# ASIGNATURA: Paradigmas y Lenguajes de Programación III (UCP - FAITA) 
# DOCENTE: Prof. Carlos Emiliano Pereyra (Carlin) 
# ARCHIVO: servidor_web.py 
# DESCRIPCIÓN: Servidor HTTP nativo con ruteo, manejo de JSON y Status Codes. 
# ============================================================================== 
 
from http.server import HTTPServer, BaseHTTPRequestHandler 
import json  
from datetime import datetime  
 
# Simulación de una base de datos de productos en memoria usando una lista de diccionarios
PRODUCTOS_DB = [
    {"id": 1, "nombre": "Hamburguesa Completa con Cheddar", "precio": 8500.0},
    {"id": 2, "nombre": "Parrillada para dos personas", "precio": 22000.0},
    {"id": 3, "nombre": "Pizza Especial de Muzzarella", "precio": 9000.0}
]
 
class PyLPApiHandler(BaseHTTPRequestHandler): 
 
    def _set_headers(self, status_code=200): 
        self.send_response(status_code)  
        self.send_header('Content-Type', 'application/json')  
        self.send_header('Access-Control-Allow-Origin', '*')  
        self.end_headers()  
 
    def do_GET(self): 
        if self.path == '/api/v1/health': 
            self._set_headers(200)  
            respuesta = { 
                "status": "online", 
                "timestamp": datetime.now().isoformat(), 
                "materia": "PyLP III - UCP Sede Posadas" 
            } 
            self.wfile.write(json.dumps(respuesta).encode('utf-8')) 
 
        elif self.path == '/api/v1/productos': 
            self._set_headers(200)  
            self.wfile.write(json.dumps(PRODUCTOS_DB).encode('utf-8')) 
 
        else: 
            self._set_headers(404)  
            error_payload = { 
                "error": "Recurso no encontrado", 
                "path_solicitado": self.path 
            } 
            self.wfile.write(json.dumps(error_payload).encode('utf-8')) 
 
    def do_POST(self): 
        if self.path == '/api/v1/productos': 
            length = int(self.headers.get('Content-Length', 0)) 
            body_bytes = self.rfile.read(length) 
 
            try: 
                data = json.loads(body_bytes.decode('utf-8')) 
 
                if "nombre" not in data or "precio" not in data: 
                    self._set_headers(400)  
                    error_val = {"error": "Bad Request: Faltan campos obligatorios 'nombre' o 'precio'"} 
                    self.wfile.write(json.dumps(error_val).encode('utf-8')) 
                    return  
 
                nuevo_producto = { 
                    "id": len(PRODUCTOS_DB) + 1, 
                    "nombre": data["nombre"], 
                    "precio": float(data["precio"]) 
                } 
                PRODUCTOS_DB.append(nuevo_producto) 
 
                self._set_headers(201)  
                self.wfile.write(json.dumps(nuevo_producto).encode('utf-8')) 
 
            except json.JSONDecodeError: 
                self._set_headers(400)  
                self.wfile.write(json.dumps({"error": "JSON mal formado en el payload"}).encode('utf-8')) 
        else: 
            self._set_headers(404) 
 
if __name__ == '__main__': 
    PUERTO = 8080 
    server = HTTPServer(('', PUERTO), PyLPApiHandler) 
    print(f"Servidor PyLP III corriendo exitosamente en http://localhost:{PUERTO}") 
    print("Endpoints listos para probar:") 
    print(f"  - GET  http://localhost:{PUERTO}/api/v1/health") 
    print(f"  - GET  http://localhost:{PUERTO}/api/v1/productos") 
    print(f"  - POST http://localhost:{PUERTO}/api/v1/productos")

    server.serve_forever()