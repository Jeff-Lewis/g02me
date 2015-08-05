## Introduction ##

Go2.me functionality is available to programmers through a JSON/Javascript API.  Most of the URL's that are supported by the user-interface have a JSON-equivalent request.

All requests are of the form:

```
http://go2.me/...?callback=MyCallback
```

to which the response will look like:

```
MyCallback({status:"OK", secsResponse:"x.xx", ...});
```

secsResponse displays the number of seconds required on the server to respond to the request.

Any request which writes data to the server additionally needs to supply an apikey, e.g.:

```
http://go2.me/...?callback=MyCallback&apikey=api~test~1~2009-12-31~44C09D058D6431E010734A8550D012B1435C2474
```

Note, the key shown expires on Dec 31, 2009, and is limited to one request per minute.  It may be used for limited testing. If you want to use the Go2.me api from a server applications, please send mail to apikey at go2.me.

Client-side API keys can be retrieved from Go2.me through the _init_ command (see below).  These keys allow up to 10 requests per minute but must originate from the same IP address that requested the key.

## Concepts ##

Go2.me stores shortened URL's and collects analytics information about user interactions with them.  Each shortened URL is assigned an _id_ (which is encoded as a base-55 number using digits, and upper and lower case letters).

### URL Info Format ###

Each URL has the following information that can be retrieved about it:

  * url: The _long_ URL
  * urlShort: The _short_ URL (e.g. http://go2.me/G)
  * id: The base-55 identifier for the shortened URL
  * title: The page title
  * created: Date url was first shortened
  * viewed: Total number of times the Go2.me URL has been accesssed/viewed
  * shared: Total number of times users have shared this URL (mapped the full URL to it's shortcut).
  * tags: Array of the top 10 most popular tags used for this URL.
  * scores: A collection of time-weighted scores based on the total activity surrounding the URL.
  * comments: A collection of user comments about the shared URL.

### Comments ###

Comments are entered in the API (and user interface) as a formatted string:

> username: comment string [tag1, tag2]

The API returns an array of comment objects with the parts extracted into distinct properties:

  * comment: The text portion of the comment string
  * user: The user name associated with the comment (or id number if anonymous)
  * tags: A comma separated list of tags
  * created: Date comment was created
  * delkey: Globally unique id which can be used to delete the comment

### Scores ###

Each URL has a collection of _scores_ associated with it, that represent a time-weighted sum of the total user activity surrounding each URL.  Scores are average hourly rates over the given time period that represent the sum of scores for various user actions:

  * Share a URL: 3 points
  * Comment on a URL: 2 points
  * View a URL: 1 point

For example, a URL that was shared onced and viewed once would have immediately have the following scores:

```
{day: 0.1138,
 week: 0.0164,
 month: 0.0037,
 year: 0.0026
}
```

Over time, without additional activity, the scores will be reduced by a factor or 2 (two) over each time period (the _half life_).

## Status Codes ##

The value of the 'status' property of the returned JSON object can be one of:

| **Code** | **Description** |
|:---------|:----------------|
| OK       | Command completed successfully |
| Fail     | Generic failure |
| Fail/NotFound | Object was not found/does not exist |
| Fail/Domain | Attempt to create a shortened URL for a forbidden domain |
| Warning/Domain | Attempt to create a shortened URL on the Go2.me domain |
| Fail/Auth/xxx | Authentication fail of type xxx.  One of "read", "write", "api", or "admin" |
| Fail/Busy/xxx | The server is unable to process requests at the rate that are being generated. xxx may specify an api key, user id, or ip address that is being limited. |
| Fail/Used | If setusername is called for a user nickname that is already in use. |

When a Failure status code is returned, the property, 'message', may contain a human readable explanation of the error.

## Methods ##

| **URL** | **Description** | **Returns** |
|:--------|:----------------|:------------|
| /       | Retrieve the set of (up to 50) most popular urls | {popular:[url\_info, ...]} |
| /init/  | Retrieve an API key for use in subsequent calls to Go2.me | {apikey:...} |
| /info/id | Retrieve information about a shortened URL id. | url\_info   |
| /map/?url=...&title=... | Generate a shorted URL from a long one. | url\_info   |
| /comment/?id=xxx&comment=text-string | Add a comment to the URL with id, xxx | url\_info   |
| /comment/delete?delkey=xxx | Remove the comment with deletion key, xxx | url\_info   |
| /cmd/setusername?username=xxx | Set the current user's nickname (or clear it if the 'username' parameter is missing |

## Examples ##

http://go2.me/init/?callback=Test

Results:
```
Test({
    "status": "OK", 
    "secsResponse": "0.15", 
    "apikey": "apiIP~64.81.170.252~10~3E6C1CCBEF9F30B9815E19D2C9D7E49C4973B8DC"
});
```

This client apikey can be used from current machine (same IP address) and allows up to 10 requests per minute from the client.

http://go2.me/cmd/setusername?username=test&callback=Test

Results:
```
Test({
    "username": "test", 
    "status": "OK", 
    "secsResponse": "0.03"
});
```

if the given username is already in use the response will be:

```
Test({
    "status": "Fail/Used", 
    "message": "Username (test) already in use"
});
```

The username can be forced to over-ride the uniqueness test by using the force=true parameter:

http://go2.me/cmd/setusername?username=test&callback=Test&force=true

http://go2.me/?callback=Test

Results:
```
Test({
    "status": "OK", 
    "secsResponse": "3.76", 
    "pages": [
        {
            "created": new Date("11/15/2008 20:54 GMT"), 
            "url": "http://www.tonywright.com/2008/startup-founder-evolution/", 
            "title": "Startup Founder Evolution - Tony Wright dot com", 
            "comments": [
                {
                    "comment": "Good points!", 
                    "user": "zzelinski", 
                    "created": new Date("11/15/2008 23:32 GMT")
                }, 
                {
                    "comment": "Sorry, you can close the Frameset by clicking the close box in the upper right.", 
                    "delkey": "dk~5961~E7FE7F6D10FBDC6C577703FFAB356402A87AF02A", 
                    "user": "mckoss", 
                    "created": new Date("11/15/2008 23:17 GMT")
                }, 
                {
                    "comment": "WTF? I don't like iframes.", 
                    "user": "youknowwhu", 
                    "created": new Date("11/15/2008 21:41 GMT")
                }
            ], 
            "tags": [], 
            "scores": {
                "week": 0.19815416341606795, 
                "year": 0.0063837153028364329, 
                "day": 0.69819712079902529, 
                "month": 0.049906189233787493
            }, 
            "shared": 1, 
            "id": "76", 
            "viewed": 45
        }, 
        ...
    ]
});
```

http://go2.me/info/G?callback=Test

Results:
```
Test({
    "status": "OK", 
    "created": new Date("10/19/2008 01:03 GMT"), 
    "url": "http://www.google.com/", 
    "title": "Google", 
    "comments": [
        {
            "comment": "The mighty search engine...", 
            "delkey": "dk~201~F546D5513B560E5EF965117046B2E04485EC14A6", 
            "user": "mckoss", 
            "created": new Date("09/03/2008 02:45 GMT")
        }
    ], 
    "tags": [], 
    "scores": {
        "week": 0.12193804049094506, 
        "year": 0.032913117370156744, 
        "day": 0.11136483457690714, 
        "month": 0.20523006874462313
    }, 
    "shared": 16, 
    "id": "G", 
    "viewed": 254
});
```

http://go2.me/map/?url=http://code.google.com/p/g02me/wiki/API&title=Edit%20API-g02me&callback=Test&apikey=api~test~1~2009-12-31~44C09D058D6431E010734A8550D012B1435C2474

Results:
```
Test({
    "status": "OK", 
    "secsResponse": "0.15", 
    "title": "API - g02me - Google Code", 
    "url": "http://code.google.com/p/g02me/wiki/API", 
    "created": new Date("10/18/2008 16:26 GMT"), 
    "comments": [
        {
            "comment": "Just updated the API to use an api key and rate thottling", 
            "delkey": "dk~7232~831D6F9F0FAD773E48673A9BE2D7E2938F09CD53", 
            "created": new Date("11/17/2008 19:26 GMT"), 
            "user": "mckoss", 
            "tags": "security,go2me,api"
        }, 
        {
            "comment": "", 
            "delkey": "dk~3023~678881DA8D8FA81369F51701A57AF1EF59463A45", 
            "created": new Date("10/22/2008 14:06 GMT"), 
            "user": "mckoss", 
            "tags": "python,tinyurl"
        }, 
        {
            "comment": "", 
            "delkey": "dk~3203~FDB8DE0C7399600865DD3D258F6A2CB11BFECFC7", 
            "created": new Date("10/22/2008 05:24 GMT"), 
            "user": "mckoss", 
            "tags": "g02me"
        }, 
        {
            "comment": "That's a good point.  But client-side cross-site scripting demands use of GET.  Solution is to add a \"developer key\" param.", 
            "delkey": "dk~2606~EE297D160498D124AFE010B582DEA9AB87AC4FC4", 
            "user": "mckoss", 
            "created": new Date("10/20/2008 04:26 GMT")
        }, 
        {
            "comment": "Funny!  The Google Bot and other crawlers will create tiny urls and comment when when they crawl this page.   Hint: Use POST instead of GET.", 
            "delkey": "dk~2421~D6A4744A7339C07026A5D280BD8E5B89B9D1553D", 
            "created": new Date("10/20/2008 02:31 GMT")
        }, 
        {
            "comment": "First draft complete", 
            "delkey": "dk~2162~3716719FA753D81E480DD725D904C79A1B406C72", 
            "user": "mckoss", 
            "created": new Date("10/16/2008 22:49 GMT")
        }
    ], 
    "tags": [
        "api", 
        "g02me", 
        "go2me", 
        "python", 
        "security", 
        "tinyurl"
    ], 
    "scores": {
        "week": 0.055869114435496241, 
        "month": 0.028691556794165341, 
        "day": 0.20155765447100918, 
        "year": 0.010469887802562347
    }, 
    "shared": 15, 
    "urlShort": "http://go2.me/1g", 
    "id": "1g", 
    "viewed": 55
});
```

http://go2.me/comment/?id=G&comment=test:This%20is%20a%20test%20comment%20%5Bsearch%2C%20engine%5D&callback=Test&apikey=api~test~1~2009-12-31~44C09D058D6431E010734A8550D012B1435C2474&force=true

Results:
```
Test({
    "status": "OK", 
    "secsResponse": "0.51", 
    "created": new Date("10/19/2008 01:03 GMT"), 
    "url": "http://www.google.com/", 
    "title": "Google", 
    "comments": [
        {
            "comment": "This is a test comment", 
            "delkey": "dk~6163~AA07EECB58B7129D89A451CEE2202529C7AB3D03", 
            "created": new Date("11/17/2008 04:58 GMT"), 
            "user": "test", 
            "tags": "search,engine"
        }, 
        {
            "comment": "The mighty search engine...", 
            "user": "mckoss", 
            "created": new Date("09/03/2008 02:45 GMT")
        }
    ], 
    "tags": [
        "engine", 
        "search"
    ], 
    "scores": {
        "week": 0.13012053774511992, 
        "year": 0.033070985209589128, 
        "day": 0.16796731080036048, 
        "month": 0.2071079570550399
    }, 
    "shared": 16, 
    "id": "G", 
    "viewed": 254
});
```

If you hit the api throttling limit the result will look like this:

```
Test({
    "status": "Fail/Busy/write", 
    "message": "Maximum request rate exceeded (1.9 per minute - 1 allowed for 24.16.108.51.write)", 
    "secsResponse": "0.05"
});
```

http://go2.me/comment/delete?delkey=dk~6163~AA07EECB58B7129D89A451CEE2202529C7AB3D03&callback=Test&apikey=api~test~1~2009-12-31~44C09D058D6431E010734A8550D012B1435C2474

Results:
```
Test({
    "status": "OK", 
    "secsResponse": "0.36", 
    "created": new Date("10/19/2008 01:03 GMT"), 
    "url": "http://www.google.com/", 
    "title": "Google", 
    ...
});
```

If the comment does not exist, the results will look like:

```
Test({
    "status": "Fail/NotFound", 
    "message": "Comment id=6163 does not exists", 
    "secsResponse": "0.20"
});
```