// g02me.js - Go2.me Link Shortening Service
// Copyright (c) Mike Koss (mckoss@startpad.org)
if (!window.console || !console.firebug)
	(function ()
		{
    var names = ["log", "debug", "info", "warn", "error", "assert", "dir", "dirxml",
    "group", "groupEnd", "time", "timeEnd", "count", "trace", "profile", "profileEnd"];

    window.console = {};
    for (var i = 0; i < names.length; ++i)
        window.console[names[i]] = function() {}
		})();

var Go2 = {
sSiteName: "Go2.me",
sCSRF: "",

SetCSRF: function(sCSRF)
	{
	Go2.sCSRF = sCSRF;
	},

SetUsername: function(sUsername)
	{
	var sd = new Go2.ScriptData('/cmd/setusername');
	Go2.TrackEvent('username');
	sd.Call({username:sUsername}, SUCallback);
		
	function SUCallback(obj)
		{
		switch (obj.status)
			{
		case 'OK':
			// Refresh the page to reset the display for the new server-set cookie
			window.location.href = window.location.href;
			break;
		case 'Fail/Used':
			if (confirm("The nickname, " + sUsername + ", is already in use.  Are you sure you want to use it?"))
				sd.Call({username:sUsername, force:true}, SUCallback);
			break;
		default:
			alert(Go2.sSiteName + ": " + obj.message);
			break;
			}
		};
	},
	
Map: function(sURL, sTitle)
	{
		location.href = '/map/?url='+encodeURIComponent(sURL)+'&title='+encodeURIComponent(sTitle);
	},
	
PostComment: function(sID, sUsername, sComment)
	{
	var sd = new Go2.ScriptData('/comment/');
	var objCall = {id:sID, csrf:Go2.sCSRF, username:sUsername, comment:sComment};
	Go2.TrackEvent('comment');

	sd.Call(objCall, PCCallback);
		
	function PCCallback(obj)
		{
		switch (obj.status)
			{
		case 'OK':
			// Refresh the page to reset the display for the new header
			window.location.href = window.location.href;
			break;
		case 'Fail/Used':
			if (confirm(obj.message + "  Are you sure you want to use it?"))
				{
				objCall.force = true;
				sd.Call(objCall, PCCallback);
				}
			break;
		default:
			alert(Go2.sSiteName + ": " + obj.message);
			break;
			}
		};
	},
	
DeleteComment: function(sDelKey)
	{
	if (!confirm("Are you sure you want to delete this comment?"))
		return;
	
	var sd = new Go2.ScriptData('/comment/delete');
	var objCall = {delkey:sDelKey, csrf:Go2.sCSRF};
	Go2.TrackEvent('comment/delete');

	sd.Call(objCall, function(obj) {
		switch (obj.status)
			{
		case 'OK':
			// Refresh the page to reset the display for the new header
			window.location.href = window.location.href;
			break;
		default:
			alert(Go2.sSiteName + ": " + obj.message);
			break;
			}
		});
	},
	
BanishId: function(sID, fBan)
	{
	if (!confirm("Are you sure you want to " + (fBan ? "banish" : "un-banish") + " this id: " + sID))
		return;
	
	var sd = new Go2.ScriptData('/admin/ban-id');
	
	sd.Call({id:sID, fBan:fBan, csrf:Go2.sCSRF}, function(obj) {
		switch (obj.status)
			{
		case 'OK':
			// Refresh the page to reset the display for the new header
			window.location.href = window.location.href;
			break;
		default:
			alert(Go2.sSiteName + ": " + obj.message);
			break;
			}
		});
	},

DisplayBars: function(widthMax)
	{
	scaleMax = 3.0;
	aBars = $("div.bar")
	
	if (aBars.length == 0)
		return;
	
	// assume first bar is the biggest!
	var width = parseFloat(aBars[0].attributes["bar_value"].nodeValue);
	if (width * scaleMax > widthMax)
		scaleMax = widthMax/width;
	
	var i = 1;
	var tm = new Go2.Timer(function()
		{
		Go2.ScaleBars(scaleMax * i /10);
		if (i == 10)
			tm.Active(false);
		i++;
		}, 75).Repeat().Active();
	},
	
ScaleBars: function(scale)
	{
	var aBars = $("div.bar")
	for (var i = 0; i < aBars.length; i++)
		{
		var divBar = aBars[i];
		width = parseFloat(divBar.attributes["bar_value"].nodeValue);
		divBar.style.width = (width*scale) + "px";
		}	
	},
	
TrackEvent: function(sEvent)
	{
	pageTracker._trackPageview('/meta/' + sEvent);
	},
	
// Extend(dest, src1, src2, ... )
// Shallow copy properties in turn into dest object
Extend: function(dest)
	{
	for (var i = 1; i < arguments.length; i++)
		{
		var src = arguments[i];
		for (var prop in src)
			{
			if (src.hasOwnProperty(prop))
				dest[prop] = src[prop];
			}
		}
	},

// Convert all top-level object properties into a URL query string.
// {a:1, b:"hello, world"} -> "?a=1&b=hello%2C%20world"
StParams: function(obj)
	{
	if (obj == undefined || obj == null)
		return "";
		
	var stDelim = "?";
	var stParams = "";
	for (var prop in obj)
		{
		if (!obj.hasOwnProperty(prop) || prop == "_anchor")
			continue;
		stParams += stDelim;
		stParams += encodeURIComponent(prop);
		if (obj[prop] != null)
			stParams += "=" + encodeURIComponent(obj[prop]);
		stDelim = "&";
		}
	if (obj._anchor)
		stParams += "#" + encodeURIComponent(obj._anchor);
	return stParams;
	},
	
// Level 2, IE, or Level 0 event models supported.
// "this" - points to target object
// 1st argument is event
// TODO: Don't I have to wrap for IE to add window.event???

fnHandlers: [],

AddEventFn: function(elem, stEvt, fnCallback, fCapture)
	{
	if (!fCapture)
		fCapture = false;
	if (elem.addEventListener)
		elem.addEventListener(stEvt, fnCallback, fCapture);
	else if (elem.attachEvent)
		elem.attachEvent('on' + stEvt, fnCallback);
	else
		elem['on' + stEvt] = fnCallback;

	Go2.fnHandlers.push({elem:elem, evt:stEvt, fn:fnCallback, fCapture:fCapture});
	return Go2.fnHandlers.length-1;
	},
	
RemoveEventFn: function(ifn)
	{
	var fnHand = Go2.fnHandlers[ifn];
	if (!fnHand)
		return;
	Go2.fnHandlers[ifn] = undefined;

	var elem = fnHand.elem;
	if (elem.removeEventListener)
		elem.removeEventListener(fnHand.evt, fnHand.fn, fnHand.fCapture);
	else if (elem.attachEvent)
		elem.detachEvent('on' + fnHand.evt, fnHand.fn);
	else
		elem['on' + fnHand.evt] = undefined;
	},

// Cookies can be quoted with "..." if they have spaces or other special characters.
// Internal quotes may be escaped with a \ character
// These routines use encodeURIComponent to safely encode and decode all special characters
SetCookie: function(name, value, days, fSecure)
	{
	var st = encodeURIComponent(name) + "=" + encodeURIComponent(value);
	if (days != undefined)
		st += ";max-age=" + days*60*60*24;
	if (fSecure)
		st += ";secure";
	st += ";path=/";
	document.cookie = st;
	},

GetCookies: function()
	{
	var st = document.cookie;
	var rgPairs = st.split(";");
	
	var obj = {};
	for (var i = 0; i < rgPairs.length; i++)
		{
		// Note that document.cookie never returns ;max-age, ;secure, etc. - just name value pairs
		rgPairs[i] = rgPairs[i].Trim();
		var rgC = rgPairs[i].split("=");
		var val = decodeURIComponent(rgC[1]);
		// Remove quotes around value string if any (and also replaces \" with ")
		var rg = val.match('^"(.*)"$');
		if (rg)
			val = rg[1].replace('\\"', '"');
		obj[decodeURIComponent(rgC[0])] = val;
		}
	return obj;
	}
};  // Go2

Go2.Timer = function(fnCallback, ms)
{
	this.ms = ms;
	this.fnCallback = fnCallback;
	return this;
};

Go2.Timer.prototype = {
	constructor: Go2.Timer,
	fActive: false,
	fRepeat: false,
	fInCallback: false,
	fReschedule: false,

Repeat: function(f)
{
	if (f == undefined)
		f = true;
	this.fRepeat = f;
	return this;
},

Ping: function()
{
	// In case of race condition - don't call function if deactivated
	if (!this.fActive)
		return;

	// Eliminate re-entrancy - is this possible?
	if (this.fInCallback)
		{
		this.fReschedule = true;
		return;
		}

	this.fInCallback = true;
	this.fnCallback();
	this.fInCallback = false;

	if (this.fActive && (this.fRepeat || this.fReschedule))
		this.Active(true);
},

// Calling Active resets the timer so that next call to Ping will be in this.ms milliseconds from NOW
Active: function(fActive)
{
	if (fActive == undefined)
		fActive = true;
	this.fActive = fActive;
	this.fReschedule = false;

	if (this.iTimer)
		{
		clearTimeout(this.iTimer);
		this.iTimer = undefined;
		}

	if (fActive)
		this.iTimer = setTimeout(this.Ping.FnMethod(this), this.ms);

	return this;
}
}; // Go2.Timer

Go2.ScriptData = function(stURL)
{
    this.stURL = stURL;
    return this;
};

Go2.ScriptData.ActiveCalls = [];
Go2.ScriptData.ridNext = 1;
Go2.ScriptData.stMsg = {
    errBusy: "Call made while another call is in progress.",
    errUnmatched: "Callback received for inactive call: ",
    errTimeout: "Server did not respond before timeout."
    };

Go2.ScriptData.prototype = {
	constructor:Go2.ScriptData,
	rid: 0,
	msTimeout: 10000, 

Call: function(objParams, fnCallback)
	{
    if (this.rid != 0)
        throw(new Error(Go2.ScriptData.stMsg.errBusy));

	this.fResponse = false;
	this.objResponse = undefined;
	this.ridResponse = 0;
   	this.rid = Go2.ScriptData.ridNext++;
    Go2.ScriptData.ActiveCalls[this.rid] = this;

	if (fnCallback)
		this.fnCallback = fnCallback;
            
    if (objParams === undefined)
            objParams = {};
    objParams.callback = "Go2.ScriptData.ActiveCalls[" + this.rid + "].Callback";
    this.script = document.createElement("script");
    this.script.src = this.stURL + Go2.StParams(objParams);
    this.tm = new Go2.Timer(this.Timeout.FnMethod(this), this.msTimeout).Active(true);
    document.body.appendChild(this.script);
    console.log("script[" + this.rid + "]: " + this.script.src);
    return this;
	},
	
Callback: function()
	{
	// Ignore callbacks for canceled/timed out or old calls
	this.fResponse = true;
	var rid = this.rid;
    this.Cancel();
    console.log("(" + rid + ") -> ", arguments);
    this.fnCallback.apply(undefined, arguments);
	},
	
Timeout: function()
	{
	rid = this.rid;
	this.Cancel();
    console.log("(" + rid + ") -> TIMEOUT");
    this.fnCallback({status:"Fail/Timeout", message:"The " + Go2.sSiteName + " server failed to respond."});
	},
	
// ScriptData can be re-used once complete
Cancel: function()
	{
	Go2.ScriptData.Cancel(this.rid);
	}
}; //Go2.ScriptData

Go2.ScriptData.Cancel = function(rid)
{
	if (rid == 0)
		return;
	var sd = Go2.ScriptData.ActiveCalls[rid];
	Go2.ScriptData.ActiveCalls[rid] = undefined;
	// Guard against multiple calls to Cancel (after sd may be reused)
	if (sd && sd.rid == rid)
		{
		sd.rid = 0;
		sd.tm.Active(false);
		}
};

// Some extensions to built-it JavaScript objects (sorry!)

Function.prototype.FnMethod = function(obj)
{
	var _fn = this;
	return function () { return _fn.apply(obj, arguments); };
};

Function.prototype.FnArgs = function()
{
	var _fn = this;
	var _args = [];
	for (var i = 0; i < arguments.length; i++)
		_args.push(arguments[i]);

	return function () {
		var args = [];
		// In case this is a method call, preserve the "this" variable
		var self = this;

		for (var i = 0; i < arguments.length; i++)
			args.push(arguments[i]);
		for (i = 0; i < _args.length; i++)
			args.push(_args[i]);

		return _fn.apply(self, args);
	};	
};

String.prototype.Trim = function()
{
	return (this || "").replace( /^\s+|\s+$/g, "");
};
