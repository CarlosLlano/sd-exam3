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
