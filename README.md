# Israel Train Coupon Bot
While coronavirus is still among us, the Israel train requires its clients to show a coupon in ever train ride.

This Telegram bot help to automate the process.

## How to run
First, install requirements
```bash
pip install -r requirements.txt
```

#### running locally
If you want to run it locally on your machine, create a config file named `config.json` and add the following fields:
```json
{
  "token": "<bot token>",
  "port": "<port>",
  "host": "<host if you run on webhook mode>",
  "num_threads": "<maximun number of threads, max is 100>",
  "polling": "<true for polling, false for webhook>",
  "admins": "[<admins telegram user id>, ...]",
  "firebase_url": "<firebase db url>"
}
```

from the same directory of `config.json` run `python bot.py` currently supporting only python 3.7

#### running on heroku
on heroku set all the following environment variables:
* `TOKEN` - bot's token
* `PORT` - port to run on
* `HOST` - host url if using webhook mode
* `POLLING` - empty string for webhook mode, True for polling mode
* `NUM_THREADS` - number of threads
* `ADMINS` - comma separated list of users ids of the admins
* `FIREBASE_URL` - firebase url


## Proxy
To enable proxy calls to the rail server, use the env variable `RAIL_PROXY` and set an https proxy server (including 
the port)

