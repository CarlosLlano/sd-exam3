# PARCIAL 3 SISTEMAS DISTRIBUIDOS #

***1. Consigne los comandos de linux necesarios para el aprovisionamiento de los servicios solicitados. En este punto,
no debe incluir archivos tipo Dockerfile solo se requiere que usted identifique los comandos o acciones que debe automatizar.***

***CONTENEDOR CONSUL***

**Funcion:** llevar registro de los servicios

```bash
docker run -d --name=consul -p 8500:8500 consul
```


***CONTENEDOR REGISTRATOR***

**Funcion:** Para cada contenedor que es iniciado, verifica sus servicios y los registra en el contenedor consul.
```bash
docker run -d \
    --name=registrator \
    --net=host \
    --volume=/var/run/docker.sock:/tmp/docker.sock \
    gliderlabs/registrator:latest \
    -internal \
      consul://localhost:8500
```

Se puede comprobar el funcionamiento de este contenedor con el siguiente comando:
```bash
docker logs registrator
```
![img1](https://user-images.githubusercontent.com/17281733/33508560-0ba4b7a0-d6c9-11e7-9b3b-ca2fbab403e3.png)

Se observa que el registrator encontro y añadio los servicios del contenedor consul. Para verificar que fueron registrados:
```bash
curl localhost:8500/v1/catalog/services
```
![img2](https://user-images.githubusercontent.com/17281733/33508612-7ca0d6b4-d6c9-11e7-82c4-b97208e9a1f3.png)


***SERVICIO WEB***

El servicio web consistirá en un script de python que lleva constancia del numero de veces que el servicio web ha sido utilizado.
```python
from flask import Flask
from redis import Redis
import os
import socket

app = Flask(__name__)
redis = Redis(host='redis', port=6379)
host = socket.gethostname()

@app.route('/')
def hello():
    count = redis.incr('hits')
    return 'Hello World! I have been seen %s times. My Host name is %s\n\n' % (count ,host)

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
```

Para almacenar y consultar esta informacion hace uso de un contenedor con la base de datos redis.



***CONTENEDOR BALANCEADOR DE CARGA***

**Funcion:** se encarga de redirigir las peticiones a cada uno de los servicios web. 
En cuanto a la implementacion se decide utilizar un contenedor con el sistema operativo centos y sobre este instalar haproxy
y consul-template. Este ultimo es necesario para actualizar el archivo de configuracion de haproxy dinamicamente.


*Tanto el contenedor con el servicio web como el contenedor que ejerce como balanceador de carga, necesitan archivos Dockerfile para
su funcionamiento. El resto de contenedores (consul, registrator y redis) unicamente requieren el uso de las imagenes publicas.*

___

***2. Escriba los archivos Dockerfile para cada uno de los servicios solicitados junto con los archivos fuente necesarios. 
Tenga en cuenta consultar buenas prácticas para la elaboración de archivos Dockerfile.***

***Dockerfile para el servicio web***
```dockerfile
FROM python:3.4-alpine
ADD . /code
WORKDIR /code
RUN pip install -r requirements.txt
CMD ["python", "app.py"]
```

***Dockerfile para el balanceador de carga***
```dockerfile
FROM centos:latest

RUN yum -y install wget && yum -y install unzip && yum -y install haproxy

ENV CONSUL_TEMPLATE_VERSION 0.19.3

ADD https://releases.hashicorp.com/consul-template/${CONSUL_TEMPLATE_VERSION}/consul-template_${CONSUL_TEMPLATE_VERSION}_SHA256SUMS /tmp/
ADD https://releases.hashicorp.com/consul-template/${CONSUL_TEMPLATE_VERSION}/consul-template_${CONSUL_TEMPLATE_VERSION}_linux_amd64.zip /tmp/

RUN cd /tmp && \
    sha256sum -c consul-template_${CONSUL_TEMPLATE_VERSION}_SHA256SUMS 2>&1 | grep OK && \
    unzip consul-template_${CONSUL_TEMPLATE_VERSION}_linux_amd64.zip && \
    mv consul-template /bin/consul-template && \
    rm -rf /tmp

WORKDIR /etc/haproxy
ADD haproxy.ctmpl .
```

Al final del dockerfile se observa que se monta un archivo llamado ***haproxy.ctmpl*** en la carpeta de configuracion de haproxy. 
Este archivo servira de plantilla para obtener dinamicamente la configuracion de haproxy. 
Para ello, contiene en su definicion de nodos, la siguiente sintaxis de consul-template:

![img3](https://user-images.githubusercontent.com/17281733/33509599-fc38d1b8-d6d0-11e7-93ed-81dd5ed5caf1.png)

Para obtener el archivo ***haproxy.cfg*** se requiere consul-template. En el punto siguiente, se detalla como utilizando esta herramienta
el balanceador puede seguir funcionando cada vez que haya un escalamiento de los servicios web.


___

***3. Escriba el archivo docker-compose.yml necesario para el despliegue de la infraestructura (10%). 
No emplee configuraciones deprecated. Incluya un diagrama general de los componentes empleados.***

El archivo docker-compose.yml automatiza los comandos vistos en el punto 1.

```yml
version: '2'
services:
  consul:
    image: consul
    container_name: consul
    ports:
    - 8500:8500

  registrator:
    image: gliderlabs/registrator:latest
    container_name: registrator
    links:
      - consul:consul
    volumes:
      - /var/run/docker.sock:/tmp/docker.sock
    command: -internal consul://consul:8500

  balanceador:
    build: haproxy/.
    container_name: balanceador
    labels:
      - "SERVICE_NAME=Balanceador"
    ports:
      - "80:80"
    links:
      - consul:consul
    command: consul-template -consul-addr=consul:8500 -template="/etc/haproxy/haproxy.ctmpl:/etc/haproxy/haproxy.cfg:/usr/sbin/haproxy -f /etc/haproxy/haproxy.cfg -D -p /var/run/haproxy.pid"

  web:
    build: web/.
    labels:
      - "SERVICE_NAME=ServicioWeb"
    ports:
      - "5000"

  redis:
    image: "redis:alpine"
    container_name: redis
    ports:
      - "6379"
```

Como aspecto adicional que aun no se habia detallado en los puntos anteriores, el balanceador de carga inicia consul-template con 
el siguiente comando:
```bash
consul-template -consul-addr=consul:8500 -template="/etc/haproxy/haproxy.ctmpl:/etc/haproxy/haproxy.cfg:/usr/sbin/haproxy -f /etc/haproxy/haproxy.cfg -D -p /var/run/haproxy.pid"
```
Con este comando el balanceador realiza varias cosas:
1. Se comunica permanentemente con el contenedor de consul 
(-consul-addr=consul:8500)

2. Establece que cada vez que se inicie o se detenga un contenedor con el servicio web, se utilice la plantilla haproxy.ctmpl para 
generar el archivo de configuracion haproxy.cfg
(-template="/etc/haproxy/haproxy.ctmpl:/etc/haproxy/haproxy.cfg:/usr/sbin/haproxy)


3. Reinicia el servicio haproxy cada vez que se actualice el archivo de configuracion
(/usr/sbin/haproxy -f /etc/haproxy/haproxy.cfg -D -p /var/run/haproxy.pid)

De esta forma, por ejemplo con un escalamiento de tres para el servicio web, consul-template puede obtener:

![ev2](https://user-images.githubusercontent.com/17281733/33510072-cda3607a-d6d5-11e7-98c7-03361caa8bb1.png)


***Diagrama general de los componentes empleados***

![captura](https://user-images.githubusercontent.com/17281733/33510592-ba58e110-d6db-11e7-883c-0c2e5c664821.PNG)


___

***4. Incluya evidencias que muestran el funcionamiento de lo solicitado.*** 

***Inicio***
```bash
docker-compose up -d
```

![evidencia1](https://user-images.githubusercontent.com/17281733/33510701-503f3840-d6dd-11e7-9f50-ed70b4430198.png)


![evidencia 2](https://user-images.githubusercontent.com/17281733/33510703-5999f628-d6dd-11e7-816b-4a9bbcb97f02.png)


![evidencia 3](https://user-images.githubusercontent.com/17281733/33510705-60fdf9b4-d6dd-11e7-9387-3e30f75afb3c.png)

Archivo haproxy.cfg

´´´bash
docker exec -it balanceador /bin/bash
cat haproxy.cfg
´´´

![evidencia4](https://user-images.githubusercontent.com/17281733/33510714-a4b277ac-d6dd-11e7-8176-4628ce501797.png)


***Escalar***

```bash
docker-compose scale web=2
```

![evidencia5](https://user-images.githubusercontent.com/17281733/33510742-00d65f58-d6de-11e7-95c4-cd51b0f1c940.png)


![evidencia8](https://user-images.githubusercontent.com/17281733/33510762-46afcd66-d6de-11e7-9132-bcff60121577.png)


![evidencia6](https://user-images.githubusercontent.com/17281733/33510765-4eb5d122-d6de-11e7-9a6f-36fccb8f6194.png)


![evidencia7](https://user-images.githubusercontent.com/17281733/33510766-582dc548-d6de-11e7-8055-8f3c802a4f0a.png)


Archivo de configuracion

![evidencia9](https://user-images.githubusercontent.com/17281733/33510772-70eba294-d6de-11e7-892a-6e194ce061f7.png)


```bash
docker-compose scale web=5
```

![ezgif com-optimize](https://user-images.githubusercontent.com/17281733/33510901-216f99d0-d6e0-11e7-88cf-4b70a6fdd0a9.gif)


```bash
docker-compose scale web=2
```

![final](https://user-images.githubusercontent.com/17281733/33511016-edcbf446-d6e1-11e7-9675-8f1043fc1c41.gif)

___

***5. Documente algunos de los problemas encontrados y las acciones efectuadas para su solución al aprovisionar
la infraestructura y aplicaciones***

**Problema:** reiniciar el servicio de haproxy 

La imagen de centos en la cual se instalo haproxy, no contenia las directivas para el manejo de servicios (service o systemctl).
Sin embargo, siempre se puede gestionar los servicios de forma directa. En el caso de haproxy, el comando que permite iniciar o reiniciar
el servicio es el siguiente:
```bash
/usr/sbin/haproxy -f /etc/haproxy/haproxy.cfg -D -p /var/run/haproxy.pid
```


