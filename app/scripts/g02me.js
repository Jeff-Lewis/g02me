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
	var objCall = {username:sUsername, urlLogin:window.location.href};
	Go2.TrackEvent('username');
	sd.Call(objCall, SUCallback);
		
	function SUCallback(obj)
		{
		switch (obj.status)
			{
		case 'OK':
			// Refresh the page to reset the display for the new server-set cookie
			if (obj.username == '')
				window.location.href = "/";
			else
				window.location.href = window.location.href;
			break;
		case 'Fail/Auth/Used':
			if (confirm("The nickname, " + sUsername + ", is already in use.  Are you sure you want to use it?"))
				{
				objCall.force = true;
				sd.Call(objCall, SUCallback);
				}
			break;
		case 'Fail/Auth/user':
			if (confirm("The nickname, " + sUsername + ", is already in use and requires a login.  Do you want to log in now?"))
				{
				window.location.href = obj.urlLogin;
				}
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
	var objCall = {
		id:sID,
		csrf:Go2.sCSRF,
		username:sUsername,
		comment:sComment,
		urlLogin: '/' + sID + '?comment=' + encodeURIComponent(sComment)
		};
	Go2.TrackEvent('comment');

	sd.Call(objCall, PCCallback);
		
	function PCCallback(obj)
		{
		switch (obj.status)
			{
		case 'OK':
			// Refresh the page to reset the display for the new header
			window.location.href = '/info/' + sID;
			break;
		case 'Fail/Auth/Used':
			if (confirm(obj.message + ".  Are you sure you want to use it?"))
				{
				objCall.force = true;
				sd.Call(objCall, PCCallback);
				}
			break;
		case 'Fail/Auth/user':
			if (confirm(obj.message + ".  Do you want to log in now?"))
				{
				window.parent.location.href = obj.urlLogin;
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
	
ParseParams: function(stURL)
	{
	var rgQuery = stURL.match(/([^?#]*)(#.*)?$/);
	if (!rgQuery) return {};
	
	var objParse = {};
	
	if (rgQuery[2])
		objParse._anchor = decodeURIComponent(rgQuery[2].substring(1));
		
	var rgParams = rgQuery[1].split("&");
	for (var i = 0; i < rgParams.length; i++)
		{
		var ich = rgParams[i].indexOf("=");
		var stName;
		var stValue;
		if (ich == -1)
			{
			stName = rgParams[i];
			stValue = "";
			continue;
			}
		else
			{
			stName = rgParams[i].substring(0, ich);
			stValue = rgParams[i].substring(ich+1);
			}
		objParse[decodeURIComponent(stName)] = decodeURIComponent(stValue);
		}
		
	return objParse;
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

Go2.optionsProfile = {
	focus: "user",
	enter: "save",
	message: "message",
	fields: {
		message:{hidden: true, value:"", type: 'message'},
		username:{label: "Nickname", type: 'text', required:true},
		comments:{label: "Page Comments", type: 'note'}
		},
	fieldsBottom: {
		captcha:{type: "captcha", required:true, labelShort:"Proof of Humanity"},
		tos:{label: 'I agree to the <a tabindex="-1" href="/terms-of-service">Terms of Service</a>',
			type: "checkbox", required:true, labelShort:"Terms of Service"}
		},
	buttons: {
		save:{label: "Save", type: 'button'}
		}
	};

// Javascript Form
// Usage:
// var db = new Go2.JSForm(divForm);
// db.Init({title:,fields:,fieldsBottom:,buttons:}, fnCallback);
// -> fnCallback(options) (fields have .value properties added)
	
Go2.JSForm = function(divForm)
{
	this.divForm = divForm;
};

Go2.JSForm.prototype = {
	constructor: Go2.JSForm,
	tokens: {
		required: " is required.",
		idPre: "_JF"
		},
	errors: [],

	htmlPatterns: {
		title: '<h1>{title}</h1>',
		text: '<label for="_JF{n}">{label}:</label><input id="_JF{n}" type="text" value="{value}"/>',
		password: '<label>{label}:</label><input id="_JF{n}" type="password"/>',
		checkbox: '<label class="checkbox" for="_JF{n}"><input id="_JF{n}" type="checkbox"/>{label}</label>',
		note: '<label>{label}:</label><textarea id="_JF{n}" rows="5">{value}</textarea>',
		captcha: '<label>What does {q} =<input id="_JF{n}" type="text"/></label>',
		message: '<span id="_JF{n}">{value}</span>',
		button: '<input type="button" value="{label}" onclick="Go2.JSForm.ButtonClick(\'{name}\');"/>'
		},

Init: function (options)
	{
	if (this.fShow)
		throw Error("Cannot re-initialize dialog box while modal dialog dispayed.");

	this.options = {};
	Go2.ExtendCopy(this.options, this.optionsDefault, options);
	this.ifld = 0;

	this.InitDiv(this.divTop, [{type: 'title', title:this.options.title}]); 
	this.InitDiv(this.divMiddle, this.options.fields);
	this.InitDiv(this.divBottom, this.options.fieldsBottom);
	this.InitDiv(this.divButtons, this.options.buttons);
	console.log(this.divClip.innerHTML);
	
	this.InitFields(this.options.fields);
	this.InitFields(this.options.fieldsBottom);
	
	this.ResizeBox(true);
	},
	
//Size the Middle section to fit the elements within it
ResizeBox: function(fHidden)
	{
	if (fHidden)
		{
		this.divClip.style.visibility = "hidden";
		this.divClip.style.display = "block";
		}
	var elt = this.divMiddle.lastChild;
	var ptMid = Go2.DOM.PtClient(this.divMiddle);
	var ptElt = Go2.DOM.PtClient(elt);
	this.dyMiddle = ptElt[1] - ptMid[1] + elt.offsetHeight + 4;
	this.divMiddle.style.height = this.dyMiddle + "px";
	if (fHidden)
		{
		this.divClip.style.display = "none";
		this.divClip.style.visibility = "visible";
		}
	},

//Additional field initialization after building HTML for the form	
InitFields: function(fields)
	{
	for (var prop in fields)
		{
		var fld = this.GetField(prop);
		
		// Hide any "hidden" fields
		if (fld.hidden)
			fld.elt.style.display = "none";
		}
	},
	
InitDiv: function(div, fields, fResize)
	{
	var stb = new Go2.StBuf();
	for (var prop in fields)
		{
		var fld = fields[prop];
		fld.n = this.ifld++;
		var keys = {q:"2+2", name:prop};
		Go2.Extend(keys, fld);
		stb.Append(Go2.ReplaceKeys(this.htmlPatterns[fld.type], keys));
		}
	div.innerHTML = stb.toString();
	},
	
FieldError: function(fld, stError)
	{
	this.errors.push({fld:fld, error:stError});
	},
	
ExtractValues: function(fields)
	{
	for (var prop in fields)
		{
		var fld = this.GetField(prop);
		if (!fld.elt)
			continue;

		switch (fld.elt.tagName.toLowerCase())
			{
		case "input":
			if (fld.elt.type == "checkbox")
				{
				fld.value = fld.elt.checked;
				if (fld.required && !fld.value)
					this.FieldError(fld, (fld.labelShort || fld.label) + this.tokens.required);
				}
			else
				{
				fld.value = fld.elt.value.Trim();
				if (fld.required && fld.value.length == 0)
					this.FieldError(fld, (fld.labelShort || fld.label) + this.tokens.required);
				}
			break;
		case "textarea":
			fld.value = fld.elt.value.Trim();
			break;
			}
		}
	},
	
ButtonClick: function(stButton)
	{
	this.errors = [];
	this.ExtractValues(this.options.fields);
	this.ExtractValues(this.options.fieldsBottom);

	if (this.errors.length > 0)
		{
		if (this.options.message)
			{
			var fld = this.GetField(this.options.message);
			fld.elt.firstChild.nodeValue = this.errors[0].error;
			fld.elt.style.display = "block";
			}
		else
			alert(this.errors[0].error);
		this.errors[0].fld.elt.focus();
		this.errors[0].fld.elt.select();
		this.ResizeBox();
		return;
		}
		
	if (this.fnCallback)
		{
		var fields = {button:stButton};
		Go2.Extend(fields, this.options.fields, this.options.fieldsBottom);
		this.fnCallback(fields);
		}
	this.Show(false);
	},
	
GetField: function(stName)
	{
	var fld = this.options.fields[stName];
	if (!fld)
		fld = this.options.fieldsBottom[stName];
	if (fld)
		fld.elt = document.getElementById(this.tokens.idPre + fld.n);
	return fld;
	},

Focus: function(evt)
	{
	this.hasFocus = evt.target;
	},
	
KeyDown: function(evt)
	{
	if (evt.keyCode == 27)
		{
		this.Show(false);
		evt.preventDefault();
		}
	
	// Hit the OK button on Enter - unless we have a textarea selected	
	if (evt.keyCode == 13 && this.options.enter &&
		this.hasFocus && this.hasFocus.tagName.toLowerCase() != "textarea")
		{
		this.ButtonClick(this.options.enter);
		evt.preventDefault();
		}
		
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
