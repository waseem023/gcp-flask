FROM python:3.10

ENV PORT 8081
ENV HOSTDIR 0.0.0.0

EXPOSE 8081

RUN apt-get update -y && \
    apt-get install -y python3-pip

COPY ./requirements.txt /app/requirements.txt

WORKDIR /app

RUN pip install -r requirements.txt

COPY . /app


ENTRYPOINT ["python", "app.py"]
