# Israel Train Coupon Bot
While coronavirus is still among us, the Israel train requires its clients to show a coupon in ever train ride.

This Telegram bot help to automate the process.

## How to run
### Run on docker
build the container
```bash
docker build -t train_bot .
```
setup a config file just as mentioned at [running locally](#running-locally)
run the container
```bash
docker run -it --rm --name train_bot_run train_bot
```



### running locally
First, install requirements
```bash
pip install -r requirements.txt
```

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

## Train API
Train API in python is available in the `train_api.py` file. These are the main function:
* `request_train`
* `get_available_trains`
* `the Train object`

You can read the docs of those function for help.

#### REST API
* ##### Reserve a seat (QR code image)
    To reserve a seat and get a QR code image one needs to send a POST request to the following url:
    `https://www.rail.co.il/taarif//_layouts/15/SolBox.Rail.FastSale/ReservedPlaceHandler.ashx?numSeats=1&smartCard={ID}&mobile={PHONE_NUMBER}&userEmail={EMAIL}&method=MakeVoucherSeatsReservation&IsSendEmail=true"&source=1&typeId=1`
    ###### Query string
    Take a note at the query string, there are 3 fields that needs to be filled:
    * `{ID}` - need to be replaced with a correct ID number (validated at the server).
    * `{PHONE_NUMBER}` - need to be replaced with a 10 digit phone number (its **not** validated in the server, so this can
     be any 10 digit number).
    * `{EMAIL}` - the users email address, this can be left blank (`""`), but if supplied, an email with confirmation of 
    the order as well as cancellation link will be sent.

    ###### Payload
    The posts request must contain a json payload with the following fields:
    ```json
    [{
            "TrainDate": "05/10/2020 00:00:00",
            "destinationStationId": "54",
            "destinationStationHe": "",
            "orignStationId": "23",
            "orignStationHe": "",
            "trainNumber": 640,
            "departureTime": "05/10/2020 18:35:00",
            "arrivalTime": "05/10/2020 19:03:00",
            "orignStation": "ראשון לציון-משה דיין",
            "destinationStation": "ת\"א השלום",
            "orignStationNum": 4600,
            "destinationStationNum": 9800,
            "DestPlatform": 2,
            "TrainOrder": 1
        }]
    ```
    Fields explanation:
    * `TrainDate` - String of the date of the train (e.g. "05\10\2020 00:00:00") the time does'nt matter.
    * `destinationStationId` - the id of the destination train station (can be found at train_api.stations_info dict at the 
    key `ID`)
    * `destinationStationHe` - name of the train station, can be left blank
    * `originStationId` - the id of the origin train station (can be found at train_api.stations_info dict at the key `ID`)
    * `originStationHe` - name of the train station, can be left blank
    * `trainNumber` - the train number
    * `departureTime` - String of the departure date and time of the train (e.g. "05\10\2020 18:35:00")
    * `arrivalTime` - String of the arribal date and time of the train (e.g. "05\10\2020 18:35:00")
    * `originStation` - name of the origin train station in hebrew (can be found at train_api.stations_info dict at the key 
    `HE`)
    * `destinationStation` - name of the destination train station in hebrew (can be found at train_api.stations_info dict
     at the key `HE`)
     * `orignStationNum` - The number of the origin train station (different from the `ID`, this can be found as key of 
     of train in the dict train_api.stations_info)
     * `desinationStationNum` - The number of the destination train station (different from the `ID`, this can be found 
     as key of train in the dict train_api.stations_info)
     * `DestPlatfrom` - the platform of the train
     * `TrainOrder` - 1
     
    Dont worry, all of this data can be obtained from the trains from the server.

    ###### Result
    The server respond with a json object:
    ```json
    {
      "BarcodeImage": "the QR image data in base64, save this into a jpeg",
      "voutcher": {
        "ErrorDescription": "Error message is any error occured"
      },
      ...
    }
    ```
    
    
    

* ##### Get list of trains from the server
    To get a list of trains, we need to send a GET request to this url:
    `https://www.rail.co.il/apiinfo/api/Plan/GetRoutes
           ?OId={origin_station_id}
           &TId={dest_station_id}
           &Date={date}
           &Hour={hour}
           &isGoing=true
           &c={unix_time}`
    
    ###### Query string
    These next fields should be replaced
    * `{origin_station_id}` - should be replaced with the origin station number (e.g 9800)
    * `{dest_station_id}` - should be replaced with the destination station number (e.g 4600)
    * `{date}` - the date to search for (e.g. 20201005)
    * `{hour}` - the hour to search for (e.g. 1630)
    * `{unix_time}` - unix time microseconds (e.g. 1601899218029).
    
    ###### Result
    Result is of the following structure:
    ```json
    {
      "Data": {
        "Routes": [
            {"Train": [...]},
            {"Train": [...]},
            {"Train": [...]}
        ]
      }  
    }
    ```
    Each item in the nested "Train" list is a train object which contains the following fields:
    * `OrignStation`- The origin station number
    * `DestinationStation` - the destination station number
    * `Trainno` - the train number
    * `DestPlatform` - the number of the destination platform
    * `DepartureTime` - the departure date and time (in format 05/10/2020 18:35:00)
    * `ArrivalTime` - the arrival date and time (in format 05/10/2020 19:03:00)
    