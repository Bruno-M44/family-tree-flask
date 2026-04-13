FROM python:3.12.3-alpine

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./

RUN pip install --upgrade pip && pip install -r requirements-dev.txt

COPY . .

EXPOSE 4000

CMD [ "flask", "run", "--host=0.0.0.0", "--port=4000"]
# CMD ["python", "run.py"]
