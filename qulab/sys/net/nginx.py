import asyncio
import os
from urllib.parse import quote_plus

from fastapi import FastAPI, Request
from fastapi.responses import Response
from pydantic import BaseModel

NGINX_DIR = 'C:/Users/Administrator/Desktop/nginx/nginx-1.20.2'
HOST_URL = 'https://systemq.baqis.ac.cn'

db = {
    "n01": {
        "notebook_port": 1000,
        "codeserver_port": 1001,
        "ip": "127.0.0.1",
        "token": "ed747047-1d9d-47b0-8fc2-b4914f8a9bd9",
    },
    "n02": {
        "notebook_port": 1002,
        "codeserver_port": 1003,
        "ip": "127.0.0.1",
        "token": "ed423dd1-05fb-48d2-a720-dbebfb2ea3e1",
    },
    "n03": {
        "notebook_port": 1004,
        "codeserver_port": 1005,
        "ip": "127.0.0.1",
        "token": "e3b0c442-98fc-11e4-8dfc-aa07a5b093d3",
    },
}


def fmt_config(ip, notebook_port, codeserver_port, local_notebook_port,
               local_codeserver_port, page):
    return """
server {""" + f"""
    listen {notebook_port} ssl;
    listen [::]:{notebook_port} ssl;
""" + """
    include ssl/ssl.conf;

    server_name  systemq.baqis.ac.cn;

    client_max_body_size 100M;

    # notebook
    location / {
        include auth/auth.conf;
""" + f"""
        proxy_pass http://{ip}:{local_notebook_port}/;""" + """
        proxy_set_header X-Real_IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-NginX-Proxy true;
        proxy_ssl_session_reuse off;
        proxy_set_header Host $http_host;

        proxy_redirect off;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /static/ {
        alias  html/_jupyter_notebook/static/;
    }

    location /login {
        include auth/auth.conf;
        default_type text/html;
        add_header Content-Type "text/html; charset=UTF-8";
""" + f"""
        return 200 "{page}";
""" + """
    }

    include auth/location.conf;
}

server {""" + f"""
    listen  {codeserver_port} ssl;
    listen [::]:{codeserver_port} ssl;
""" + """
    include ssl/ssl.conf;

    server_name  systemq.baqis.ac.cn;

    client_max_body_size 100M;

    # vscode
    location / {
        include auth/auth.conf;
""" + f"""
        proxy_pass http://{ip}:{local_codeserver_port}/;""" + """
        proxy_set_header X-Real_IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-NginX-Proxy true;
        proxy_ssl_session_reuse off;
        proxy_set_header Host $http_host;

        proxy_redirect off;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /oss-dev/static/out/ {
        root   html;
    }

    include auth/location.conf;
}
"""


def fmt_page(notebook_url, codeserver_url):
    return """
<!DOCTYPE html>
<html>
<head>
<title>Welcome to systemq!</title>
<style>
body {
    width: 35em;
    margin: 0 auto;
    font-family: Tahoma, Verdana, Arial, sans-serif;
}
</style>
</head>
<body>
<h1>Welcome to systemq!</h1>""" + f"""
<a href=\\"{notebook_url}\\">notebook</a>.<br/>
<a href=\\"{codeserver_url}\\">codeserver</a>.<br/>
</body>
</html>
"""


class Node(BaseModel):
    token: str
    name: str
    notebook_port: int = 8888
    codeserver_port: int = 14263
    codeserver_path: str = ""


app = FastAPI()


@app.post("/auth")
async def auth(request: Request, node: Node):
    try:
        assert node.name in db
        assert node.token == db[node.name]['token']
        notebook_port = db[node.name]['notebook_port']
        codeserver_port = db[node.name]['codeserver_port']

        ip = request.client.host
        if ip == db[node.name]['ip']:
            return Response(status_code=200)
        else:
            print("    CHANGE IP", db[node.name]['ip'], "===>", ip)
            db[node.name]['ip'] = ip

        #ip = request.headers.get('x-real-ip')
        local_notebook_port = node.notebook_port
        local_codeserver_port = node.codeserver_port
        codeserver_path = quote_plus(node.codeserver_path)

        codeserver_url = f"{HOST_URL}:{codeserver_port}?tkn=lZBAQISFF532&folder={codeserver_path}"
        notebook_url = f"{HOST_URL}:{notebook_port}/tree"

        page = fmt_page(notebook_url, codeserver_url)
        page = ''.join(page.splitlines())

        config = fmt_config(ip, notebook_port, codeserver_port,
                            local_notebook_port, local_codeserver_port, page)

        with open(f"{NGINX_DIR}/conf/servers/{node.name}.conf", "w") as f:
            f.write(config)

        await asyncio.sleep(0.1)

        cwd = os.getcwd()

        os.chdir(NGINX_DIR)

        os.system(f'{NGINX_DIR}/nginx.exe -s reload')

        os.chdir(cwd)

        return Response(status_code=200)
    except:
        return Response(status_code=400)
