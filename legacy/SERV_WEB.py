#============================================================================== 
# ASIGNATURA: Paradigmas y Lenguajes de Programación III (UCP - FAITA) 
# DOCENTE: Prof. Carlos Emiliano Pereyra (Carlin) 
# ARCHIVO: servidor_web.py 
# DESCRIPCIÓN: Servidor HTTP nativo con ruteo, manejo de JSON y Status Codes. 
# ============================================================================== 
 
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

# Memoria temporal para los productos
productos_db = [
    {"id": 1, "nombre": "Milanesa Napolitana", "precio": 9000.0}
]

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == '/api/v1/productos':
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(productos_db).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/api/v1/productos':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                
                # --- VALIDACIÓN TIPO AE1 ---
                precio = float(data.get("precio", 0))
                if precio <= 0:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "El precio debe ser mayor a 0."}).encode('utf-8'))
                    return
                # -----------------------------

                nuevo_id = len(productos_db) + 1
                nuevo_producto = {
                    "id": nuevo_id,
                    "nombre": data.get("nombre"),
                    "precio": precio
                }
                productos_db.append(nuevo_producto)

                self.send_response(201)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(nuevo_producto).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Datos inválidos"}).encode('utf-8'))

def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Servidor PyLP III corriendo exitosamente en http://localhost:{port}")
    httpd.serve_forever()

if __name__ == '__main__':
    run()