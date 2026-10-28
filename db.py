import os
import mysql.connector

def get_db_connection():
    host = os.getenv("DB_HOST", "localhost")

    config = {
        "host": host,
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME", "booknest"),
    }

    if host != "localhost" and host != "127.0.0.1":
        config.update({
            "ssl_ca": os.path.join(
                os.path.dirname(__file__), "isrgrootx1.pem"
            ),
            "ssl_verify_cert": True,
            "ssl_verify_identity": True,
        })

    return mysql.connector.connect(**config)