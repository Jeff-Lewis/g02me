// g02me.js - G02.ME Link Shortening Service
// Copyright (c) Mike Koss (mckoss@startpad.org)
if (!window.console || !console.firebug)
{
    var names = ["log", "debug", "info", "warn", "error", "assert", "dir", "dirxml",
    "group", "groupEnd", "time", "timeEnd", "count", "trace", "profile", "profileEnd"];

    window.console = {};
    for (var i = 0; i < names.length; ++i)
        window.console[names[i]] = function() {}
}

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

var G02 = {
sSiteName: "G02.ME",

SetUsername: function(sUsername)
	{
	var sd = new G02.ScriptData('/cmd/setusername');
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
			alert(G02.sSiteName + ": " + obj.message);
			break;
			}
		};
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

	G02.fnHandlers.push({elem:elem, evt:stEvt, fn:fnCallback, fCapture:fCapture});
	return G02.fnHandlers.length-1;
	},
	
RemoveEventFn: function(ifn)
	{
	var fnHand = G02.fnHandlers[ifn];
	if (!fnHand)
		return;
	G02.fnHandlers[ifn] = undefined;

	var elem = fnHand.elem;
	if (elem.removeEventListener)
		elem.removeEventListener(fnHand.evt, fnHand.fn, fnHand.fCapture);
	else if (elem.attachEvent)
		elem.detachEvent('on' + fnHand.evt, fnHand.fn);
	else
		elem['on' + fnHand.evt] = undefined;
	}
};  // G02

G02.Timer = function(fnCallback, ms)
{
	this.ms = ms;
	this.fnCallback = fnCallback;
	return this;
};

G02.Timer.prototype = {
	constructor: G02.Timer,
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
}; // G02.Timer

G02.ScriptData = function(stURL)
{
    this.stURL = stURL;
    return this;
};

G02.ScriptData.ActiveCalls = [];
G02.ScriptData.ridNext = 1;
G02.ScriptData.stMsg = {
    errBusy: "Call made while another call is in progress.",
    errUnmatched: "Callback received for inactive call: ",
    errTimeout: "Server did not respond before timeout."
    };

G02.ScriptData.prototype = {
	constructor:G02.ScriptData,
	rid: 0,
	msTimeout: 2000, 

Call: function(objParams, fnCallback)
	{
    if (this.rid != 0)
        throw(new Error(G02.ScriptData.stMsg.errBusy));

	this.fResponse = false;
	this.objResponse = undefined;
	this.ridResponse = 0;
   	this.rid = G02.ScriptData.ridNext++;
    G02.ScriptData.ActiveCalls[this.rid] = this;

	if (fnCallback)
		this.fnCallback = fnCallback;
            
    if (objParams === undefined)
            objParams = {};
    objParams.callback = "G02.ScriptData.ActiveCalls[" + this.rid + "].Callback";
    this.script = document.createElement("script");
    this.script.src = this.stURL + G02.StParams(objParams);
    this.tm = new G02.Timer(G02.ScriptData.Cancel.FnArgs(this.rid), this.msTimeout).Active(true);
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
	
Timeout: function(rid)
	{
	if (rid != this.rid)
		return;
	this.Cancel();
    console.log("(" + rid + ") -> TIMEOUT");
    this.fnCallback({status:"Fail/Timeout"});
	},
	
// ScriptData can be re-used once complete
Cancel: function()
	{
	G02.ScriptData.Cancel(this.rid);
	}
}; //G02.ScriptData

G02.ScriptData.Cancel = function(rid)
{
	if (rid == 0)
		return;
	var sd = G02.ScriptData.ActiveCalls[rid];
	G02.ScriptData.ActiveCalls[rid] = undefined;
	// Guard against multiple calls to Cancel (after sd may be reused)
	if (sd && sd.rid == rid)
		{
		sd.rid = 0;
		sd.tm.Active(false);
		}
};
