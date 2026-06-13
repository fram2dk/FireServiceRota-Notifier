# syntax=docker/dockerfile:1
   
FROM python:3.15.0a8-slim
WORKDIR /
COPY requirements.txt ./

RUN pip install --no-cache-dir pip==26.0.1 && \
    pip install --no-cache-dir -r requirements.txt
    # Note: we had to merge the two "pip install" package lists here, otherwise
    # the last "pip install" command in the OP may break dependency resolution…
RUN apt update && apt install -y less nano sqlite3


WORKDIR /app
COPY ./app ./

#CMD ["bash", "test.sh"]
CMD ["python3", "main.py"]
