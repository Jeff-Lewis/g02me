// g02me.js - G02.ME Link Shortening Service
// Copyright (c) Mike Koss (mckoss@startpad.org)

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
		// BUG: This is a bit bogus to encode a query param in JSON
		if (typeof obj[prop] == "object")
			stParams += "=" + encodeURIComponent(PF.EncodeJSON(obj[prop], true));
		else if (obj[prop] != null)
			stParams += "=" + encodeURIComponent(obj[prop]);
		stDelim = "&";
		}
	if (obj._anchor)
		stParams += "#" + encodeURIComponent(obj._anchor);
	return stParams;
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
