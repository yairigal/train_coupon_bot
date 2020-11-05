FROM python:3.8

ADD . /app
WORKDIR /app

RUN apt-get install git -y
RUN git clone https://github.com/yairigal/train_coupon_bot

WORKDIR /app/train_coupon_bot

RUN pip install --no-cache-dir -r requirements.txt
COPY config.json .
CMD [ "python", "./bot.py" ]