import psycopg2
from psycopg2 import pool, OperationalError
import time
import threading
from config import cargar_config

class DatabasePool:
    _instance = None
    _pool = None
    _lock = threading.Lock()
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def _ensure_initialized(self):
        if not self._initialized:
            config = cargar_config()
            if not config:
                raise Exception("No hay configuración de red. Configure la conexión desde el login.")
            self.db_params = {
                "host": config["db_host"],
                "port": config["db_port"],
                "dbname": config["db_name"],
                "user": config["db_user"],
                "password": config["db_password"]
            }
            self._create_pool()
            self._initialized = True
    
    def _create_pool(self):
        self._pool = pool.SimpleConnectionPool(1, 10, **self.db_params)
    
    def get_connection(self):
        self._ensure_initialized()
        try:
            return self._pool.getconn()
        except OperationalError:
            for i in range(5):
                time.sleep(2)
                try:
                    self._create_pool()
                    return self._pool.getconn()
                except:
                    continue
            raise Exception("No se pudo conectar al servidor PostgreSQL. Verifique red e IP.")
    
    def return_connection(self, conn):
        if conn:
            self._pool.putconn(conn)

db_pool = DatabasePool()

def ejecutar_consulta(query, params=None, fetchone=False, fetchall=False):
    conn = None
    try:
        conn = db_pool.get_connection()
        cur = conn.cursor()
        cur.execute(query, params or ())
        if fetchone:
            result = cur.fetchone()
        elif fetchall:
            result = cur.fetchall()
        else:
            conn.commit()
            result = None
        cur.close()
        return result
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            db_pool.return_connection(conn)