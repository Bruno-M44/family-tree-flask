FROM python:3.12.3-alpine

WORKDIR /app

COPY requirements.txt ./

RUN pip install --upgrade pip

RUN pip install -r requirements.txt

COPY . .

EXPOSE 4000

CMD [ "flask", "run", "--debug", "--host=0.0.0.0", "--port=4000"]
# CMD ["python", "run.py"]

