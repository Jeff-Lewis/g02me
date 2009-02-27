// g02me.js - Go2.me Link Shortening Service
// Copyright (c) Mike Koss (mckoss@startpad.org)

// Define stubs for FireBug objects if not present
if (!window.console || !console.firebug)
	{
	(function ()
		{
    var names = ["log", "debug", "info", "warn", "error", "assert", "dir", "dirxml",
    "group", "groupEnd", "time", "timeEnd", "count", "trace", "profile", "profileEnd"];

    window.console = {};
    for (var i = 0; i < names.length; ++i)
    	{
        window.console[names[i]] = function() {};
        }
		})();
	}

//--------------------------------------------------------------------------
// Go2.me Application Functions
//--------------------------------------------------------------------------

var Go2 = {
	sSiteName: "Go2.me",
	sCSRF: "",
	//Ignore the first load of the frame - that's likely our initial link (or just reset to initial link)
	fResetFrame: true,
	msLoaded: new Date().getTime(),
	msNextIdle: new Date().getTime(),
	msServerOffset: 0,
	// Non-empty for private conversation
	sPrivateKey: "",
	fInIdle: false,

Browser: {
	version: parseInt(window.navigator.appVersion),
	fIE: window.navigator.appName.indexOf("Microsoft") !== -1
},

Init: function(sUsername, sCSRF)
	{
	Go2.sUsername = sUsername;
	Go2.sCSRF = sCSRF;
	},
	
BeforeUnload: function(evt)
	{
	var msUnloading = new Date().getTime();
	
	if (msUnloading - Go2.msLoaded < 5000)
		{
		evt = evt || window.event || {};
		evt.returnValue = "Click CANCEL to keep the " + Go2.sSiteName + " window open.";
		return evt.returnValue;
		}
	},

Click: function()
	{
	Go2.msLoaded = 0;
	},

// Bind DOM elements by identifier 	
partIDs: ["username", "content", "content-iframe", "info", "comment", "comments", "border-v", "comment-form", "sponsor-panel", "linkLabel"],
parts: [],
BindDOM: function()
	{
	for (var i = 0; i < Go2.partIDs.length; i++)
		{
		var sID = Go2.partIDs[i];
		Go2.parts[sID] = document.getElementById(sID);
		}
	},
	
MapLoaded: function()
	{
	window.onbeforeunload = Go2.BeforeUnload;
	Go2.AddEventFn(window, "click", Go2.Click, true);
	
	try {
		Go2.location = google.loader.ClientLocation;
	} catch (e) {}
	
	Go2.BindDOM();

	if (Go2.parts["username"])
		{
		Go2.AddEventFn(Go2.parts["username"], "keydown", function(evt) {
			if (evt.keyCode == 13)
				Go2.SetUsername(Go2.parts["username"].value);
			});
		}

	var objParams = Go2.ParseParams(window.location.href);
    if (objParams.comment)
    	{
    	Go2.parts["comment"].value = objParams.comment;
    	}

	Go2.parts["comment"].focus();
	Go2.AddEventFn(Go2.parts["comment"], "keydown", Go2.KeyDownComment);
	Go2.AddEventFn(Go2.parts["content-iframe"], "load", Go2.OnNavigate);

	Go2.OnResize();
	Go2.InitPanels();
	Go2.AddEventFn(window, "resize", Go2.OnResize);
	
	Go2.UpdatePrivacy();
	Go2.DOM.ScrollToBottom(Go2.parts["comments"]);
	
	Go2.UpdatePresence();
	
	Go2.tmIdle = new Go2.Timer(500, Go2.OnIdle).Repeat().Active();
	},

ObjCallDefault: function()
	{
	var objCall = {
		id: Go2.map.id,
		since: Go2.ISO.FromDate(Go2.map.dateRequest),
		csrf: Go2.sCSRF,
		username: Go2.sUsername,
		scope: Go2.sPrivateKey
		};

	if (Go2.location)
		{
		objCall.location = Go2.location.address.city + ", " +
			Go2.location.address.region + ", " + Go2.location.address.country;
		}
	return objCall;
	},
	
OnIdle: function()
	{
	var ms = new Date().getTime();
	
	if (ms < Go2.msNextIdle || Go2.fInIdle)
		return;
	
	Go2.fInIdle = true;
	
	// Check if the user has changed the hash key at the end of the URL
	Go2.UpdatePrivacy();

	var sd = new Go2.ScriptData('/' + Go2.map.id);
	var objCall = Go2.ObjCallDefault();

	sd.Call(objCall, function(obj)
		{
		switch (obj.status)
			{
		case 'OK':
			// Assume server received request at same time as our local call
			Go2.SetServerTime(obj.dateRequest, sd.dCall);
			Go2.UpdateComments(obj);
			Go2.msNextIdle = (new Date().getTime()) + 5000;
			break;
		default:
			// Tell the user there's a problem - an back off for 1 minute.
			Go2.Notify(Go2.sSiteName + ": " + obj.message);
			Go2.msNextIdle = (new Date().getTime()) + 60*1000;
			break;
			}

		Go2.fInIdle = false;
		});
	},
	
Notify: function(s)
	{
	var pNote = document.createElement('p');
	var dNow = Go2.LocalToServerTime(new Date());
	pNote.innerHTML = s + ' - <span class="server-time" go2_ms="' + dNow.getTime() + '">?</span>'
	Go2.parts["comments"].appendChild(pNote);
	Go2.UpdateCommentTimes();
	Go2.DOM.ScrollToBottom(Go2.parts["comments"]);
	},
	
SetServerTime: function(dServer, dLocal)
	{
	Go2.msServerOffset = dServer.getTime() - dLocal.getTime();
	},
	
LocalToServerTime: function(dLocal)
	{
	var d = new Date(dLocal.getTime() + Go2.msServerOffset);
	return d;
	},
	
OnResize: function()
	{
	var rcWindow = Go2.DOM.RcWindow();
	var dyMax = rcWindow[3] - rcWindow[1];

	var ptComments = Go2.DOM.PtClient(Go2.parts["comments"]);
	var ptCommentForm = Go2.DOM.PtSize(Go2.parts["comment-form"]);
	var ptSponsor = Go2.DOM.PtSize(Go2.parts["sponsor-panel"]);
	var dyComments = dyMax - ptCommentForm[1] - ptSponsor[1] - ptComments[1];
	
	// Info bar needs to be taller than the window - force a scroll bar
	if (dyComments < 120)
		{
		dyMax += 120 - dyComments;
		dyComments = 120;
		}

	var ptContent = Go2.DOM.PtClient(Go2.parts["content"]);
	Go2.parts["content"].style.height = (dyMax - ptContent[1]) + "px";
	Go2.parts["info"].style.height = (dyMax-32) + "px";
	Go2.parts["border-v"].style.height = (dyMax-32) + "px";
	Go2.parts["comments"].style.height = dyComments + "px";
	
	Go2.DOM.ScrollToBottom(Go2.parts["comments"]);
	},
	
KeyDownComment: function(evt)
	{
	if (evt.keyCode == 13)
		{
		Go2.PostComment();
		evt.preventDefault();
		}
	},
	
OnNavigate: function()
	{
	// Can't get URL of user-navigated frame due to browser security.
	if (Go2.fResetFrame)
		{
		Go2.fResetFrame = false;
		return;
		}
	
	Go2.parts["linkLabel"].innerHTML = "Original Link";
	},
	
ResetFrame: function()
	{
	Go2.msLoaded = new Date().getTime();
	Go2.parts["content-iframe"].src = "{{map.Href}}";
	Go2.fResetFrame = true;

	Go2.parts["linkLabel"].innerHTML = "Link";
	},

SetUsername: function(sUsername)
	{
	var sd = new Go2.ScriptData('/cmd/setusername');
	var objCall = {username:sUsername, urlLogin:window.location.href};
	sd.Call(objCall, SUCallback);
	Go2.TrackEvent('username');
		
	function SUCallback(obj)
		{
		switch (obj.status)
			{
		case 'OK':
			// Refresh the page to reset the display for the new server-set cookie
			window.location.reload();
			break;
		case 'Fail/Auth/Logout':
			window.location.href = obj.urlLogout;
			break;
		case 'Fail/Auth/Used':
			if (window.confirm("The nickname, " + sUsername + ", is already in use.  Are you sure you want to use it?"))
				{
				objCall.force = true;
				sd.Call(objCall, SUCallback);
				}
			break;
		case 'Fail/Auth/user':
			if (window.confirm("The nickname, " + sUsername + ", is already in use and requires a login.  Do you want to log in now?"))
				{
				window.location.href = obj.urlLogin;
				}
			break;
		default:
			window.alert(Go2.sSiteName + ": " + obj.message);
			break;
			}
		}
	},
	
Map: function(sURL, sTitle)
	{
	window.location.href = '/map/?url='+encodeURIComponent(sURL)+'&title='+encodeURIComponent(sTitle);
	},
	
PostComment: function()
	{
	var sd = new Go2.ScriptData('/comment/');
	
	var sUsername = Go2.sUsername;
	
	if (Go2.parts["username"])
		sUsername = Go2.parts["username"].value;
	
	sComment = Go2.parts["comment"].value;

	var objCall = Go2.ObjCallDefault();
	Go2.Extend(objCall, {
		comment:sComment,
		urlLogin: '/' + Go2.map.id + '?comment=' + encodeURIComponent(sComment)
		});
	
	sd.Call(objCall, function (obj)
		{
		switch (obj.status)
			{
		case 'OK':
			Go2.CheckReload();
			Go2.parts["comment"].value = "";
			Go2.SetServerTime(obj.dateRequest, sd.dCall);
			Go2.UpdateComments(obj);
			break;
		case 'Fail/Auth/Used':
			if (window.confirm(obj.message + ".  Are you sure you want to use it?"))
				{
				objCall.force = true;
				sd.Call(objCall, PCCallback);
				}
			break;
		case 'Fail/Auth/user':
			if (window.confirm(obj.message + ".  Do you want to log in now?"))
				{
				window.parent.location.href = obj.urlLogin;
				}
			break;
		default:
			window.alert(Go2.sSiteName + ": " + obj.message);
			break;
			}
		});
	
	Go2.TrackEvent('comment');
	},

// Need to reload to set the username form or get rid of an old query string	
CheckReload: function()
	{
	if (window.location.search)
		{
		window.location.href = window.location.pathname + window.location.hash;
		return;
		}
	var mCookies = Go2.GetCookies();
	if (!mCookies['username'])
		mCookies['username'] = '';
	if (Go2.sUsername != mCookies['username'])
		window.location.reload(); 
	},
	
// Format a date as an age (how long ago)
Age: function(d, dNow)
	{
	if (!dNow)
		dNow = new Date();
	var ms = dNow.getTime() - d.getTime();
	
    if (ms < 0)
        return "in the future?";
        
    var days = Math.floor(ms/1000/60/60/24);
    var months = Math.floor(days*12/365);
    var years = Math.floor(days/365);
    
    if (years >= 1)
        return years + " year" + Go2.SPlural(years) + " ago";
    if (months >= 3)
        return months + " months ago"; 
    if (days == 1)
        return "yesterday";
    if (days > 1)
        return days + " days ago"
    hrs = Math.floor(ms/1000/60/60);
    if (hrs >= 1)
        return hrs + " hour" + Go2.SPlural(hrs) + " ago"
    minutes = Math.round(ms/1000/60);
    if (minutes < 1)
        return "seconds ago"
    return minutes + " minute" + Go2.SPlural(minutes) + " ago";
	},
	
SPlural: function(n)
	{
	return n != 1 ? 's' : '';
	},
	
DeleteComment: function(id, sDelKey)
	{
	if (!window.confirm("Are you sure you want to delete this comment?"))
		return;
	
	var sd = new Go2.ScriptData('/comment/delete');
	var objCall = Go2.ObjCallDefault();
	Go2.Extend(objCall, {
		delkey: sDelKey
		});

	sd.Call(objCall, function(obj) {
		switch (obj.status)
			{
		case 'OK':
			Go2.SetServerTime(obj.dateRequest, sd.dCall);
			Go2.UpdateComments(obj);
			$('#cmt_' + id).remove();
			break;
		default:
			Go2.Notify(Go2.sSiteName + ": " + obj.message);
			break;
			}
		});

	Go2.TrackEvent('comment/delete');
	},
	
BanishId: function(sID, fBan)
	{
	if (!window.confirm("Are you sure you want to " + (fBan ? "banish" : "un-banish") + " this id: " + sID))
		{
		return;
		}
	
	var sd = new Go2.ScriptData('/admin/ban-id');
	
	sd.Call({id:sID, fBan:fBan, csrf:Go2.sCSRF}, function(obj) {
		switch (obj.status)
			{
		case 'OK':
			// Refresh the page to reset the display for the new header
			window.location.href = window.location.href;
			break;
		default:
			window.alert(Go2.sSiteName + ": " + obj.message);
			break;
			}
		});
	},

DisplayBars: function(widthMax)
	{
	var scaleMax = 3.0;
	var aBars = $('.bar');
	var aBarHolders = $('.bar-holders');
	
	if (aBars.length === 0)
		{
		return;
		}
	
	for (var i = 0; i < aBarHolders.length; i++)
		{
		var divHolder = aBarHolders[i];
		divHolder.style.width = widthMax + "px";
		}
	
	// Find the widest bar to set max scaling
	var width = 0;
	for (i = 0; i < aBars.length; i++)
		{
		var divBar = aBars[i];
		var widthT = parseFloat(divBar.getAttribute('bar_value'));
		if (widthT > width)
			{
			width = widthT;
			}
		}

	if (width * scaleMax > widthMax)
		{
		scaleMax = widthMax/width;
		}
	
	i = 1;
	var tm = new Go2.Timer(75, function()
		{
		Go2.ScaleBars(scaleMax * i /10);
		if (i === 10)
			{
			tm.Active(false);
			}
		i++;
		}).Repeat().Active();
	},
	
ScaleBars: function(scale)
	{
	var aBars = $('.bar');
	for (var i = 0; i < aBars.length; i++)
		{
		var divBar = aBars[i];
		var width = parseFloat(divBar.getAttribute('bar_value'));
		divBar.style.width = (width*scale) + "px";
		}	
	},
	
TrackEvent: function(sEvent)
	{
	try
		{
		pageTracker._trackPageview('/meta/' + sEvent);
		}
	catch (e) {}
	},
	
FacebookShare: function(u, t)
	{
	window.open('http://www.facebook.com/sharer.php?u='+encodeURIComponent(u)+'&t='+encodeURIComponent(t),'sharer','toolbar=0,status=0,width=626,height=436');
	},
	
InitPanels: function()
	{
	var aPanels = $('.panel');
	for (var i = 0; i < aPanels.length; i++)
		{
		var divPanel = aPanels[i];
		var divExpander = $(divPanel).find('.expander')[0];
		var divHeader = $(divPanel).find('.panel-header')[0];
		var divBody = $(divPanel).find('.panel-body')[0];
		
		// Don't allow text selection in panel header
		if (divHeader)
			{
			Go2.AddEventFn(divHeader, 'mousedown', function(evt) {
				evt.preventDefault();
				evt.stopPropagation();
				});
			}
		
		// Use capture to take precedence over other panel-header clicks!
		Go2.AddEventFn(divExpander, 'mousedown', Go2.TogglePanel.FnArgs(divBody), true);
		}
	},
	
TogglePanel: function(evt, divBody)
	{
	var divExpander = evt.target;
	if (divBody.style.height === '0px')
		{
		divExpander.className = 'expander expanded';
		divBody.style.height = 'auto';
		}
	else
		{
		divExpander.className = 'expander collapsed';
		divBody.style.height = "0px";
		}
	
	Go2.OnResize();
	evt.preventDefault();
	evt.stopPropagation();
	},
	
TogglePrivate: function(sID, sUser)
	{
	var divComments = $('#comments')[0];
	Go2.sPrivateKey.sPrivateKey = Go2.sPrivateKey.Trim();

	if (Go2.sPrivateKey === "")
		{
		var sKey = window.prompt("Enter a security word to be used to access a private conversation:", sUser);
		sKey = Go2.Slugify(sKey)
		if (!sKey)
			{
			return;
			}
		window.location.hash = sKey;
		}
	else
		{
		if (!window.confirm("Are you sure you want to return to the public conversation for this link?"))
			{
			return;
			}
		// BUG: Browser is reloading the page here - not really desired.
		window.location.hash = "";
		}

	Go2.UpdatePrivacy();
	},
	
UpdatePrivacy: function()
	{
	var imgLock = $('#private-image')[0];
	var divComments = $('#comments')[0];
	
	var spanChatTitle = $('#chat-title')[0];
	
	var sNewKey = Go2.Slugify(window.location.hash);
	if (Go2.sPrivateKey === sNewKey)
		{
		return;
		}
	
	Go2.sPrivateKey = sNewKey;
	if (sNewKey)
		{
		window.location.hash = sNewKey;
		}

	if (Go2.sPrivateKey === '')
		{
		imgLock.src = "/images/lock_open.png";
		imgLock.title = "Create Private Link";
		$(divComments).removeClass('private');
		spanChatTitle.innerHTML = "Chat";
		}
	else
		{
		imgLock.src = "/images/lock.png";
		imgLock.title = "Go2 Public Link";
		$(divComments).addClass('private');
		spanChatTitle.innerHTML = "Chat (Private)"
		Go2.DOM.RemoveChildren(divComments);
		}
	},
	
UpdateComments: function(map)
	{
	var comment;
	
	if (map.comments)
		{
		for (var i = 0; i < map.comments.length; i++)
			{
			comment = map.comments[i];
			if (comment.created > Go2.map.dateRequest)
				Go2.AppendComment(comment);
			}
		}
	
	Go2.UpdateCommentTimes();
	Go2.map = map;
	
	Go2.UpdatePresence();
	},
	
UpdateCommentTimes: function()
	{
	// Update all the displayed comment dates
	spanTimes = $(".server-time");
	var dBase = Go2.LocalToServerTime(new Date());
	var d = new Date();
	
	for (i = 0; i < spanTimes.length; i++)
		{
		var span = spanTimes[i];
		d.setTime(parseInt(span.getAttribute('go2_ms')))
		span.innerHTML = Go2.Age(d, dBase);
		}
	},
	
UpdatePresence: function()
	{
	var divPres = $('#presence')[0];
	if (!Go2.map.presence)
		{
		divPres.innerHTML = "Nobody home?";
		return;
		}
	
	var st = new Go2.StBuf();

	if (Go2.map.presence)
		{
		for (i = 0; i < Go2.map.presence.length; i++)
			{
			var user = Go2.map.presence[i];
			st.Append('<img id="pres_' + user.id + '" src="' + user.thumb + '"');
			var sHover = "";
			var sSep = "";
			if (user.username)
				{
				sHover += user.username;
				sSep = " ";
				}
			if (user.location)
				sHover += sSep + "(" + user.location + ")";
			if (sHover != "")
				{
				sHover = Go2.EscapeHTML(sHover);
				st.Append(' title="' + sHover + '" alt="' + sHover + '"');
				}
			st.Append('>');
			}
		divPres.innerHTML = st.toString();
		}
	},

AppendComment: function(comment)
	{
	var st = new Go2.StBuf();
	
	var pComment = document.createElement('p');
	pComment.id = "cmt_" + comment.id;
	
	if (comment.user)
		st.Append('<a target="_top" href="/user/' + comment.user + '" title="' + comment.user + '\'s activity">' + comment.user + '</a>:');
	st.Append(' ' + Go2.Urlize(Go2.EscapeHTML(comment.comment)));
	if (comment.tags)
		{
		st.Append(' [');
		var sSep = '';
		for (var i = 0; i < comment.tags.length; i++)
			{
			tag = comment.tags[i];
			st.Append(sSep + '<a target="_top" href="/tag/' + tag + '" title="' + tag + ' pages">' + tag + '</a>')
			sSep = ', ';
			}
		st.Append(']');
		}
	st.Append(' - <span class="server-time" go2_ms="' + comment.created.getTime() + '">?</span>');
	if (comment.delkey)
		{
		st.Append(' <img class="x" onclick="Go2.DeleteComment(' + comment.id + ', \'' + comment.delkey + '\');" src="/images/x.png"/>');
		}
	
	pComment.innerHTML = st.toString();
	Go2.parts["comments"].appendChild(pComment);
	Go2.DOM.ScrollToBottom(Go2.parts["comments"]);
	},

//         1     23                                    45                      6                                                                                                     7 
reDomain: /(.*)\b((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})|(([a-z0-9][a-z0-9-]*\.)+([a-z]{2}|aero|asia|biz|cat|com|coop|edu|gov|info|int|jobs|mil|mobi|museum|net|org|pro|tel|travel)))\b(.*)$/i,	
reURL: /(.*)\b(https?:\/\/\S+)\b(.*)$/i,
reEmail: /(.*)\b(\S+@)([a-z0-9][a-z0-9-]*\.)+([a-z]{2}|aero|asia|biz|cat|com|coop|edu|gov|info|int|jobs|mil|mobi|museum|net|org|pro|tel|travel)\b(.*)$/i,
sURLPattern: '<a href="{href}">{trim}</a>&nbsp;' +
			 '<a title="New {site} Page" target="_blank" href="/map/?url={href}"><img class="inline-link" src="/images/go2me-link.png"></a>',
sEmailPattern: '<a href="mailto:{email}">{email}</a>',
	
Urlize: function(s)
	{
	var aMatch;
	
	var aWords = s.split(/\s/);
	
	for (var i = 0; i < aWords.length; i++)
		{
		var word = aWords[i];
		if (aMatch = word.match(Go2.reURL))
			{
			aWords[i] = aMatch[1] + Go2.ReplaceKeys(Go2.sURLPattern, {href:aMatch[2], trim:aMatch[2], site:Go2.sSiteName}) +
				aMatch[3];
			continue;
			}
		if (aMatch = word.match(Go2.reEmail))
			{
			aWords[i] = aMatch[1] + Go2.ReplaceKeys(Go2.sEmailPattern, {email:aMatch[2]+aMatch[3]+aMatch[4]}) +
				aMatch[5];
			continue;
			}
		if (aMatch = word.match(Go2.reDomain))
			{
			aWords[i] = aMatch[1] +
				Go2.ReplaceKeys(Go2.sURLPattern, {href:'http://' + aMatch[2], trim:aMatch[2], site:Go2.sSiteName}) +
				aMatch[7];
			continue;
			}
		}
	return aWords.join(' ');
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
				{
				dest[prop] = src[prop];
				}
			}
		}
	},

// Convert all top-level object properties into a URL query string.
// {a:1, b:"hello, world"} -> "?a=1&b=hello%2C%20world"
StParams: function(obj)
	{
	if (obj === undefined || obj === null)
		{
		return "";
		}
		
	var stDelim = "?";
	var stParams = "";
	for (var prop in obj)
		{
		if (!obj.hasOwnProperty(prop) || prop === "_anchor")
			{
			continue;
			}
		stParams += stDelim;
		stParams += encodeURIComponent(prop);
		if (obj[prop] !== null)
			{
			stParams += "=" + encodeURIComponent(obj[prop]);
			}
		stDelim = "&";
		}
	if (obj._anchor)
		{
		stParams += "#" + encodeURIComponent(obj._anchor);
		}
	return stParams;
	},
	
ParseParams: function(stURL)
	{
	var rgQuery = stURL.match(/([^?#]*)(#.*)?$/);
	if (!rgQuery)
		{
		return {};
		}
	
	var objParse = {};
	
	if (rgQuery[2])
		{
		objParse._anchor = decodeURIComponent(rgQuery[2].substring(1));
		}
		
	var rgParams = rgQuery[1].split("&");
	for (var i = 0; i < rgParams.length; i++)
		{
		var ich = rgParams[i].indexOf("=");
		var stName;
		var stValue;
		if (ich === -1)
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
		{
		fCapture = false;
		}

	if (elem.addEventListener)
		{
		elem.addEventListener(stEvt, fnCallback, fCapture);
		}
	else if (elem.attachEvent)
		{
		elem.attachEvent('on' + stEvt, fnCallback);
		}
	else
		{
		elem['on' + stEvt] = fnCallback;
		}

	Go2.fnHandlers.push({elem:elem, evt:stEvt, fn:fnCallback, fCapture:fCapture});
	return Go2.fnHandlers.length-1;
	},
	
RemoveEventFn: function(ifn)
	{
	var fnHand = Go2.fnHandlers[ifn];
	if (!fnHand)
		{
		return;
		}
	Go2.fnHandlers[ifn] = undefined;

	var elem = fnHand.elem;
	if (elem.removeEventListener)
		{
		elem.removeEventListener(fnHand.evt, fnHand.fn, fnHand.fCapture);
		}
	else if (elem.attachEvent)
		{
		elem.detachEvent('on' + fnHand.evt, fnHand.fn);
		}
	else
		{
		elem['on' + fnHand.evt] = undefined;
		}
	},

// Cookies can be quoted with "..." if they have spaces or other special characters.
// Internal quotes may be escaped with a \ character
// These routines use encodeURIComponent to safely encode and decode all special characters
SetCookie: function(name, value, days, fSecure)
	{
	var st = encodeURIComponent(name) + "=" + encodeURIComponent(value);
	if (days !== undefined)
		{
		st += ";max-age=" + days*60*60*24;
		}

	if (fSecure)
		{
		st += ";secure";
		}

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
			{
			val = rg[1].replace('\\"', '"');
			}
		obj[decodeURIComponent(rgC[0])] = val;
		}
	return obj;
	},
	
// Converts to lowercase, removes non-alpha chars and converts spaces to hyphens"
Slugify: function(s)
	{
	s = s.Trim().toLowerCase();
    s = s.replace(/[^\w\s-]/g, '-')
    	.replace(/[-\s]+/g, '-')
    	.replace(/(^-+)|(-+$)/g, '');
    return s;
	},

// Javascript Enumeration
// Build an object whose properties are mapped to successive integers
// Also allow setting specific values by passing integers instead of strings.
// e.g. new Go2.Enum("a", "b", "c", 5, "d") -> {a:0, b:1, c:2, d:5}
Enum: function(aEnum)
	{
	if (!aEnum)
		return;

	var j = 0;
	for (var i = 0; i < aEnum.length; i++)
		{
		if (typeof aEnum[i] == "string")
			this[aEnum[i]] = j++;
		else
			j = aEnum[i];
		}
	},

// Return an integer as a string using a fixed number of digits, c. (require a sign with fSign).
SDigits: function(val, c, fSign)
	{
	var s = "";
	var fNeg = (val < 0);

	if (fNeg)
		val = -val;
	
	val = Math.floor(val);
	
	for (; c > 0; c--)
		{
		s = (val%10) + s;
		val = Math.floor(val/10);
		}
		
	if (fSign || fNeg)
		s = (fNeg ? "-" : "+") + s;

	return s;
	},
	
EscapeHTML: function(s)
	{
	s = s.toString();
	s = s.replace(/&/g, '&amp;');
	s = s.replace(/</g, '&lt;');
	s = s.replace(/>/g, '&gt;');
	s = s.replace(/\"/g, '&quot;');
	s = s.replace(/'/g, '&#39;');
	return s;
	},
	
// Replace keys in dictionary of for {key} in the text string.
ReplaceKeys: function(st, keys)
	{
	for (var key in keys)
		st = st.StReplace("{" + key + "}", keys[key]);
	st = st.replace(/\{[^\{\}]*\}/g, "");
	return st;
	}
};  // Go2

//--------------------------------------------------------------------------
// Fast string concatenation buffer
//--------------------------------------------------------------------------
Go2.StBuf = function()
{
	this.rgst = [];
	this.Append.apply(this, arguments);
};

Go2.StBuf.prototype = {
constructor: Go2.StBuf,

Append: function()
	{
	for (var ist = 0; ist < arguments.length; ist++)
		this.rgst.push(arguments[ist].toString());
	return this;
	},
	
Clear: function ()
	{
	this.rgst = [];
	},

toString: function()
	{
	return this.rgst.join("");
	}
}; // Go2.StBuf


//--------------------------------------------------------------------------
// DOM Functions
// Points (pt) are [x,y]
// Rectangles (rc) are [xTop, yLeft, xRight, yBottom]
//--------------------------------------------------------------------------

Go2.DOM = {
// Get absolute position on the page for the upper left of the element.
PtClient: function(elt)
	{
	var pt = [0,0];

	while (elt.offsetParent !== null)
		{
		pt[0] += elt.offsetLeft;
		pt[1] += elt.offsetTop;
		elt = elt.offsetParent;
		}
	return pt;
	},

// Return size of a DOM element in a Point - includes borders, but not margins
PtSize: function(elt)
	{
	return [elt.offsetWidth, elt.offsetHeight];
	},

// Return absolute bounding rectangle for a DOM element: [x, y, x+dx, y+dy]
RcClient: function(elt)
	{
	var rc = Go2.DOM.PtClient(elt);
	var ptSize = Go2.DOM.PtSize(elt);
	rc.push(rc[0]+ptSize[0], rc[1]+ptSize[1]);
	return rc;
	},
	
PtMouse: function(evt)
	{
	var x = document.documentElement.scrollLeft || document.body.scrollLeft;
	var y = document.documentElement.scrollTop || document.body.scrollTop;
	return [x+evt.clientX, y+evt.clientY];
	},
	
RcWindow: function()
	{
	var x = document.documentElement.scrollLeft || document.body.scrollLeft;
	var y = document.documentElement.scrollTop || document.body.scrollTop;
	var dx = window.innerWidth || document.documentElement.clientWidth ||	document.body.clientWidth;
	var dy = window.innerHeight || document.documentElement.clientHeight || document.body.clientHeight;
	return [x, y, x+dx, y+dy];
	},
	
SetAbsPosition: function(elt, pt)
	{
	elt.style.top = pt[1] + 'px';
	elt.style.left = pt[0] + 'px';
	},
	
SetSize: function(elt, pt)
	{
	elt.style.width = pt[0] + 'px';
	elt.style.height = pt[1] + 'px';
	},
	
SetRc: function(elt, rc)
	{
	this.SetAbsPosition(elt, Go2.Vector.UL(rc));
	this.SetSize(elt, Go2.Vector.Size(rc));
	},
	
RemoveChildren: function(node)
	{
	for (var child = node.firstChild; child; child = node.firstChild)
		{
		node.removeChild(child);
		}
	},

// Set focus() on element, but NOT at the expense of scrolling the window position
SetFocusIfVisible: function(elt)
	{
	var rcElt = Go2.DOM.RcClient(elt);
	var rcWin = Go2.DOM.RcWindow();
	
	if (Go2.Vector.PtInRect(Go2.Vector.UL(rcElt), rcWin) ||
		Go2.Vector.PtInRect(Go2.Vector.LR(rcElt), rcWin))
		{
		elt.focus();
		}
	},
	
ScrollToBottom: function(elt)
	{
	elt.scrollTop = elt.scrollHeight;
	}
}; // Go2.DOM

// --------------------------------------------------------------------------
// Vector Functions
// --------------------------------------------------------------------------

Go2.Vector = {
SubFrom: function(v1, v2)
	{
	for (var i = 0; i < v1.length; i++)
		{
		v1[i] = v1[i] - v2[i];
		}
	return v1;
	},

Sub: function(v1, v2)
	{
	
	var vDiff = Go2.Vector.Copy(v1);
	return Go2.Vector.SubFrom(vDiff, v2);
	},

//In-place vector addition	
AddTo: function(vSum)
	{
	for (var iarg = 1; iarg < arguments.length; iarg++)
		{
		var v = arguments[iarg];
		for (var i = 0; i < v.length; i++)
			{
			vSum[i] += v[i];
			}
		}
	return vSum;
	},	

//Add corresponding elements of all arguments	
Add: function()
	{
	var vSum = Go2.Vector.Copy(arguments[0]);
	var args = Go2.Vector.Copy(arguments);
	args[0] = vSum;
	return Go2.Vector.AddTo.apply(undefined, args);
	},
	
//Return new vector with element-wise max
//All arguments must be same dimensioned array
//TODO: Allow mixing scalars - share code with Mult - iterator/callback pattern
Max: function()
	{
	var vMax = Go2.Vector.Copy(arguments[0]);
	for (var iarg = 1; iarg < arguments.length; iarg++)
		{
		var v = arguments[iarg];
		for (var i = 0; i < vMax.length; i++)
			{
			if (v[i] > vMax[i])
				{
				vMax[i] = v[i];
				}
			}
		}
	return vMax;
	},

//Multiply corresponding elements of all arguments (including scalars)
//All vectors must be the same dimension (length).
Mult: function()
	{
	var vProd = 1;
	var i;

	for (var iarg = 0; iarg < arguments.length; iarg++)
		{
		var v = arguments[iarg];
		if (typeof v === "number")
			{
			// Mult(scalar, scalar)
			if (typeof vProd === "number")
				{
				vProd *= v;
				}
			// Mult(vector, scalar)
			else
				{
				for (i = 0; i < vProd.length; i++)
					{
					vProd[i] *= v;
					}
				}				
			}
		else
			{
			// Mult(scalar, vector)
			if (typeof vProd === "number")
				{
				var vT = vProd;
				vProd = Go2.Vector.Copy(v);
				for (i = 0; i < vProd.length; i++)
					{
					vProd[i] *= vT;
					}
				}
			// Mult(vector, vector)
			else
				{
				if (v.length !== vProd.length)
					{
					throw new Error("Mismatched Vector Size");
					}
				for (i = 0; i < vProd.length; i++)
					{
					vProd[i] *= v[i];
					}
				}
			}
		}
	return vProd;
	},
	
Floor: function(v)
	{
	var vFloor = [];
	for (var i = 0; i < v.length; i++)
		{
		vFloor[i] = Math.floor(v[i]);
		}
	return vFloor;
	},
	
DotProduct: function()
	{
	var v = Go2.Vector.Mult.apply(undefined, arguments);
	var s = 0;
	for (var i = 0; i < v.length; i++)
		{
		s += v[i];
		}
	return s;
	},

//Append all arrays into a new array (Append(v) is same as Copy(v)
Append: function()
	{
	var vAppend = [];
	for (var iarg = 0; iarg < arguments.length; iarg++)
		{
		var v = arguments[iarg];
		for (var i = 0; i < v.length; i++)
			{
			vAppend.push(v[i]);
			}
		}
	return vAppend;
	},

//Do a (shallow) comparison of two arrays	
Equal: function(v1, v2)
	{
	for (var i = 0; i < v1.length; i++)
		{
		if (v1[i] !== v2[i])
			{
			return false;
			}
		}
	return true;
	},
	
//Routines for dealing with Points [x, y] and Rects [left, top, bottom, right]

UL: function(rc)
	{
	return rc.slice(0, 2);
	},
	
LR: function(rc)
	{
	return rc.slice(2, 4);
	},
	
Size: function(rc)
	{
	return Go2.Vector.Sub(Go2.Vector.LR(rc), Go2.Vector.UL(rc));
	},
	
NumInRange: function(num, numMin, numMax)
	{
	return num >= numMin && num <= numMax;
	},
	
PtInRect: function(pt, rc)
	{
	return Go2.Vector.NumInRange(pt[0], rc[0], rc[2]) &&
		Go2.Vector.NumInRange(pt[1], rc[1], rc[3]);
	},
	
//Return pt (1-scale) * UL + scale * LR
PtCenter: function(rc, scale)
	{
	if (scale === undefined)
		{
		scale = 0.5;
		}
	if (typeof scale === "number")
		{
		scale = [scale, scale];
		}
	var pt = Go2.Vector.Mult(scale, Go2.Vector.LR(rc));
	scale = Go2.Vector.Sub([1,1], scale);
	Go2.Vector.AddTo(pt, Go2.Vector.Mult(scale, Go2.Vector.UL(rc)));
	return pt;
	},

//Return the bounding box of the collection of pt's and rect's passed in	
BoundingBox: function()
	{
	var vPoints = Go2.Vector.Append.apply(undefined, arguments);
	if (vPoints.length % 2 !== 0)
		{
		throw Error("Invalid arguments to BoundingBox");
		}
	
	var ptMin = vPoints.slice(0,2),
		ptMax = vPoints.slice(0,2);

	for (var ipt = 2; ipt < vPoints.length; ipt += 2)
		{
		var pt = vPoints.slice(ipt, ipt+2);
		if (pt[0] < ptMin[0])
			{
			ptMin[0] = pt[0];
			}
		if (pt[1] < ptMin[1])
			{
			ptMin[1] = pt[1];
			}
		if (pt[0] > ptMax[0])
			{
			ptMax[0] = pt[0];
			}
		if (pt[1] > ptMax[1])
			{
			ptMax[1] = pt[1];
			}
		}

	return [ptMin[0], ptMin[1], ptMax[0], ptMax[1]];
	}
}; // Go2.Vector

//Synonym - Copy(v) is same as Append(v)
Go2.Vector.Copy = Go2.Vector.Append;

//--------------------------------------------------------------------------
// Timer Functions
//--------------------------------------------------------------------------

Go2.Timer = function(ms, fnCallback)
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
	if (f === undefined)
		{
		f = true;
		}
	this.fRepeat = f;
	return this;
},

Ping: function()
{
	// In case of race condition - don't call function if deactivated
	if (!this.fActive)
		{
		return;
		}

	// Eliminate re-entrancy - is this possible?
	if (this.fInCallback)
		{
		this.fReschedule = true;
		return;
		}

	this.fInCallback = true;
	try
		{
		this.fnCallback();
		}
	catch (e)
		{
		console.log("Error in timer callback: " + e.message + "(" + e.name + ")");
		}
	this.fInCallback = false;

	if (this.fActive && (this.fRepeat || this.fReschedule))
		{
		this.Active(true);
		}
},

// Calling Active resets the timer so that next call to Ping will be in this.ms milliseconds from NOW
Active: function(fActive)
{
	if (fActive === undefined)
		{
		fActive = true;
		}
	this.fActive = fActive;
	this.fReschedule = false;

	if (this.iTimer)
		{
		window.clearTimeout(this.iTimer);
		this.iTimer = undefined;
		}

	if (fActive)
		{
		this.iTimer = window.setTimeout(this.Ping.FnMethod(this), this.ms);
		}

	return this;
}
}; // Go2.Timer

//--------------------------------------------------------------------------
// AJAX Helper Functions
//--------------------------------------------------------------------------

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
    if (this.rid !== 0)
    	{
        throw(new Error(Go2.ScriptData.stMsg.errBusy));
        }

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
    this.tm = new Go2.Timer(this.msTimeout, this.Timeout.FnMethod(this)).Active(true);
    this.dCall = new Date();
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
	var rid = this.rid;
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
	if (rid === 0)
		{
		return;
		}
	var sd = Go2.ScriptData.ActiveCalls[rid];
	Go2.ScriptData.ActiveCalls[rid] = undefined;
	// Guard against multiple calls to Cancel (after sd may be reused)
	if (sd && sd.rid === rid)
		{
		sd.rid = 0;
		sd.tm.Active(false);
		}
};

//--------------------------------------------------------------------------
// ISO 8601 Date Formatting
// YYYY-MM-DDTHH:MM:SS.sssZ (where Z could be +HH or -HH for non UTC)
// Note that dates are inherently stored at UTC dates internally.  But we infer that they
// denote local times by default.  If the dt.__tz exists, it is assumed to be an integer number
// of hours offset to the timezone for which the time is to be indicated (e.g., PST = -08).
// Callers should set dt.__tz = 0 to fix the date at UTC.  All other times are adjusted to
// designate the local timezone.
//--------------------------------------------------------------------------
Go2.ISO = {
	tz: -(new Date().getTimezoneOffset())/60,  // Default timezone = local timezone
	enumMatch: new Go2.Enum([1, "YYYY", "MM", "DD", 5, "hh", "mm", 8, "ss", 10, "sss", "tz"]),

FromDate: function(dt, fTime)
	{
	var dtT = new Date();
	dtT.setTime(dt.getTime());
	var tz = dt.__tz;
	if (tz == undefined)
		tz = Go2.ISO.tz;

	// Adjust the internal (UTC) time to be the local timezone (add tz hours)
	// Note that setTime() and getTime() are always in (internal) UTC time.
	if (tz)
		dtT.setTime(dtT.getTime() + 60*60*1000 * tz);
	
	var s = dtT.getUTCFullYear() + "-" + Go2.SDigits(dtT.getUTCMonth()+1,2) + "-" + Go2.SDigits(dtT.getUTCDate(),2);
	var ms = dtT % (24*60*60*1000);
	if (ms || fTime || tz != 0)
		{
		s += "T" + Go2.SDigits(dtT.getUTCHours(),2) + ":" + Go2.SDigits(dtT.getUTCMinutes(),2);
		ms = ms % (60*1000);
		if (ms)
			s += ":" + Go2.SDigits(dtT.getUTCSeconds(),2);
		if (ms % 1000)
			s += "." + Go2.SDigits(dtT.getUTCMilliseconds(), 3);
		if (tz == 0)
			s += "Z";
		else
			s += Go2.SDigits(tz, 2, true);
		}
	return s;
	},

//--------------------------------------------------------------------------
// Parser is more lenient than formatter.  Punctuation between date and time parts is optional.
// We require at the minimum, YYYY-MM-DD.  If a time is given, we require at least HH:MM.
// YYYY-MM-DDTHH:MM:SS.sssZ as well as YYYYMMDDTHHMMSS.sssZ are both acceptable.
// Note that YYYY-MM-DD is ambiguous.  Without a timezone indicator we don't know if this is a
// UTC midnight or Local midnight.  We default to UTC midnight (the FromDate function always
// write out non-UTC times so we can append the time zone).
// Fractional seconds can be from 0 to 6 digits (microseconds maximum)
//--------------------------------------------------------------------------
ToDate: function(sISO, objExtra)
	{
	var e = Go2.ISO.enumMatch;
	var aParts = sISO.match(/^(\d{4})-?(\d\d)-?(\d\d)(T(\d\d):?(\d\d):?((\d\d)(\.(\d{0,6}))?)?(Z|[\+-]\d\d))?$/);
	if (!aParts)
		return undefined;

	aParts[e.mm] = aParts[e.mm] || 0;
	aParts[e.ss] = aParts[e.ss] || 0;
	aParts[e.sss] = aParts[e.sss] || 0;
	// Convert fractional seconds to milliseconds
	aParts[e.sss] = Math.round(+('0.'+aParts[e.sss])*1000);
	if (!aParts[e.tz] || aParts[e.tz] === "Z")
		aParts[e.tz] = 0;
	else
		aParts[e.tz] = parseInt(aParts[e.tz]);
	
	// Out of bounds checking - we don't check days of the month is correct!	
	if (aParts[e.MM] > 59 || aParts[e.DD] > 31 || aParts[e.hh] > 23 || aParts[e.mm] > 59 || aParts[e.ss] > 59 ||
		aParts[e.tz] < -23 || aParts[e.tz] > 23)
		return undefined;
	
	var dt = new Date();
	dt.setUTCFullYear(aParts[e.YYYY], aParts[e.MM]-1, aParts[e.DD]);
	if (aParts[e.hh])
		{
		dt.setUTCHours(aParts[e.hh], aParts[e.mm], aParts[e.ss], aParts[e.sss]);
		}
	else
		dt.setUTCHours(0,0,0,0);

	// BUG: For best compatibility - could set tz to undefined if it is our local tz
	// Correct time to UTC standard (utc = t - tz)
	dt.__tz = aParts[e.tz];
	if (aParts[e.tz])
		dt.setTime(dt.getTime() - dt.__tz * (60*60*1000));
	if (objExtra)
		Go2.Extend(dt, objExtra);
	return dt;
	}
};  // Go2.ISO

//--------------------------------------------------------------------------
// Some extensions to built-it JavaScript objects (sorry!)
//--------------------------------------------------------------------------

// Wrap a method call in a function
Function.prototype.FnMethod = function(obj)
{
	var _fn = this;
	return function () { return _fn.apply(obj, arguments); };
};

// Append additional arguments to a function
Function.prototype.FnArgs = function()
{
	var _fn = this;
	var _args = [];
	for (var i = 0; i < arguments.length; i++)
		{
		_args.push(arguments[i]);
		}

	return function () {
		var args = [];
		// In case this is a method call, preserve the "this" variable
		var self = this;

		for (var i = 0; i < arguments.length; i++)
			{
			args.push(arguments[i]);
			}
		for (i = 0; i < _args.length; i++)
			{
			args.push(_args[i]);
			}

		return _fn.apply(self, args);
	};	
};

String.prototype.Trim = function()
{
	return (this || "").replace( /^\s+|\s+$/g, "");
};

String.prototype.StReplace = function(stPat, stRep)
{

	var st = "";

	var ich = 0;
	var ichFind = this.indexOf(stPat, 0);

	while (ichFind >= 0)
		{
		st += this.substring(ich, ichFind) + stRep;
		ich = ichFind + stPat.length;
		ichFind = this.indexOf(stPat, ich);
		}
	st += this.substring(ich);

	return st;
};
