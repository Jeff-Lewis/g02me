// unit.js - Unit testing framework
// Copyright (c) 2007-2008, Mike Koss (mckoss@pageforest.com)
//
// Usage:
// ts = new pf.TestSuite("Suite Name");
// ts.DWOutputDiv();
// ts.AddTest("Test Name", function(ut) { ... ut.Assert() ... });
// ...
// ts.Run();
// ts.Report();
//
// Requires: base.js, timer.js

// UnitTest - Each unit test calls a function which in turn calls
// back Assert's on the unit test object.

PF.UnitTest = function (stName, fn)
{
    this.stName = stName;
    this.fn = fn;
    this.rgres = [];
};

PF.UnitTest.states = {
    created: 0,
    running: 1,
    completed: 2
};

PF.UnitTest.prototype = {
constructor: PF.UnitTest,
    state: PF.UnitTest.states.created,
    cErrors: 0,
    cErrorsExpected: 0,
    cAsserts: 0,
    fEnable: true,
    cAsync: 0,
    fThrows: false,
    cThrows: 0,
    msTimeout: 20000,
    stTrace: "",
    cBreakOn: 0,
    fStopFail: false,

Run: function(ts)
    {
    var fCaught = false;

    if (!this.fEnable)
        return;
    this.state = PF.UnitTest.states.running;

    if (this.cAsync)
        this.tm = new PF.Timer(this.Timeout.FnCallback(this), this.msTimeout).Active();

    try
        {
        this.fn(this);
        }
    catch (e)
        {
        fCaught = true;
        this.fStopFail = false;		// Avoid recursive asserts
        this.e = e;
        this.Async(0)
        if (this.fThrows)
            this.AssertException(this.e, this.stThrows);
        else
            {
            var stMsg = "Exception: " + e.name + " (" + e.message;
            if (e.number != undefined)
                stMsg += ", Error No:" + (e.number & 0xFFFF);
            stMsg += ")";
            if (e.lineNumber != undefined)
                stMsg += " @ line " + e.lineNumber;
            this.Assert(false, stMsg);
            }
        }
    
    if (this.fThrows && !fCaught)
        this.Assert(false, "Missing expected Exception: " + this.stThrows);

    if (!this.cAsync)
        this.state = PF.UnitTest.states.completed;
    },
    
IsComplete: function()
    {
    return !this.fEnable || this.state == PF.UnitTest.states.completed;
    },

AssertThrown: function()
    {
    this.AssertGT(this.cThrows, 0, "Expected exceptions not thrown.");
    this.cThrows = 0;
    },

Enable: function(f)
    {
    this.fEnable = f;
    return this;
    },
    
StopFail: function(f)
	{
	this.fStopFail = f;
	return this;
	},

// Change expected number async events running - test is finish at 0.
// Async(false) -> -1
// Async(true) -> +1
// Async(0) -> set cAsync to zero
// Async(c) -> +c
// TODO: Could use Expected number of calls to Assert to terminate an async test
// instead of relying on the cAsync count going to zero.
Async: function(dc, msTimeout)
    {
    if (dc == undefined || dc === true)
        dc = 1;
    if (dc === false)
    	dc = -1;
    if (msTimeout)
    	{
		// Don't call assert unless we have a failure - would mess up user counts for numbers
		// of Asserts expected.
    	if (this.cAsync != 0 || this.state == PF.UnitTest.states.running)
    		this.Assert(false, "Test error: Async timeout only allowed at test initialization.");
    	this.msTimeout = msTimeout;
    	}
    if (dc == 0)
    	this.cAsync = 0;
    else
	    this.cAsync += dc;
    if (this.cAsync < 0)
    	{
		this.Assert(false, "Test error: unbalanced calls to Async")
		this.cAsync = 0;    	
    	}

	// When cAsync goes to zero, the aynchronous test is complete
    if (this.cAsync == 0 && this.state == PF.UnitTest.states.running)
        this.state = PF.UnitTest.states.completed;
        
    this.CheckValid();
    return this;
    },
    
Timeout: function()
{
    if (this.cAsync > 0)
        {
        this.fStopFail = false;
        this.Async(0);
        this.Assert(false, "Async test timed out.");
        }
},

Throws: function(stThrows)
    {
    this.fThrows = true;
    this.stThrows = stThrows;
    this.CheckValid();
    return this;
    },

Expect: function(cErrors, cTests)
    {
    this.cErrorsExpected = cErrors;
    this.cTestsExpected = cTests;
    return this;
    },

CheckValid: function()
    {
    if (this.cAsync > 0 && this.fThrows)
        this.Assert(false, "Test error: can't test async thrown exceptions.");
    },
    
Reference: function(url)
    {
    this.urlRef = url;
    return this;
    },

// All asserts bottleneck to this function
// Eror line pattern "N. [Trace] Note (Note2)"
Assert: function(f, stNote, stNote2)
    {
    // TODO: is there a way to get line numbers out of the callers?
    // A backtrace (outside of unit.js) would be the best way to designate
    // the location of failing asserts.
    if (this.stTrace)
    	stNote = (this.cAsserts+1) + ". [" + this.stTrace + "] " + stNote;
    else
    	stNote = (this.cAsserts+1) + ". " + stNote;

    if (stNote2)
    	stNote += " (" + stNote2 + ")";
    	
    // Allow the user to set a breakpoint when we hit a particular failing test
    if (!f && (this.cBreakOn == -1 || this.cBreakOn == this.cAsserts+1))
    		this.Breakpoint(stNote);
    
    var res = new PF.TestResult(f, this, stNote);
    this.rgres.push(res);
    if (!res.f)
        this.cErrors++;
    this.cAsserts++;
    // We don't throw an exception on StopFail if we already have thrown one!
    if (this.fStopFail && this.cErrors > this.cErrorsExpected && !this.e)
    	{
    	this.fStopFail = false;
    	this.Async(0);
    	throw new Error("StopFail - test terminates on first (unexpected) failure.");
    	}
    },
    
Trace: function(stTrace)
	{
	this.stTrace = stTrace;
	},
	
BreakOn: function(cBreakOn)
	{
	this.cBreakOn = cBreakOn;
	},
	
// Set Firebug breakpoint in this function
Breakpoint: function(stNote)
	{
	console.log("unit.js Breakpoint: [" + this.stName + "] " + stNote);
	// Set Firebug breakpoint on this line:
	var x = 1;
	},

AssertEval: function(stEval)
    {
    this.Assert(eval(stEval), stEval);
    },

// v1 is the quantity to be tested against the "known" quantity, v2.
AssertEq: function(v1, v2, stNote)
    {
    if (typeof v2 != "object")
        {
        this.Assert(v1 == v2, v1 + " == " + v2, stNote);
        return;
        }

    if (typeof v1 != "object")
        {
        this.Assert(false, "Expected Object for comparison: " + typeof v1);
        return;
        }

    this.AssertContains(v1, v2);
    var cProp1 = this.PropCount(v1);
    var cProp2 = this.PropCount(v2);
    this.Assert(cProp1 == cProp2, "Objects have different property counts (" + cProp1 + " != " + cProp2 + ")");
    
    // Make sure Dates match
    if (v1.constructor == Date)
    	{
	    this.AssertEq(v2.constructor, Date);   	
    	if (v2.constructor == Date)
    		this.AssertEq(v1.toString(), v2.toString());
    	}
    },

PropCount: function(obj)
    {
    var cProp = 0;
    for (var prop in obj)
        {
        if (obj.hasOwnProperty(prop))
            cProp++;
        }
    return cProp;
    },

// Assert that objAll contains all the (top level) properties of objSome
AssertContains: function(objAll, objSome)
    {
    if (typeof objAll != "object")
        {
        this.Assert(false, "Expected Object for comparison: " + typeof objAll);
        return;
        }

    if (typeof objSome != "object")
        {
        this.Assert(false, "Expected comparison to be Object: " + typeof objSome);
        return;
        }
    
    for (var prop in objSome)
        {
        if (!objSome.hasOwnProperty(prop))
            continue;
        this.AssertEq(objAll[prop], objSome[prop]);
        }
    },
    
AssertIdent: function(v1, v2)
    {
    this.Assert(v1 === v2, v1 + " === " + v2);
    },

AssertNEq: function(v1, v2)
    {
    this.Assert(v1 != v2, v1 + " != " + v2);
    },

AssertGT: function(v1, v2)
    {
    this.Assert(v1 > v2, v1 + " > " + v2);
    },
    
AssertLT: function(v1, v2)
	{
	this.Assert(v1 < v2, v1 + " < " + v2);
	},

AssertFn: function(fn)
    {
    var stFn = fn.toString();
    stFn = stFn.substring(stFn.indexOf("{")+1, stFn.lastIndexOf("}")-1);
    this.Assert(fn(), stFn);
    },
    
// Useage: ut.AssertThrows(<type>, function(ut) {...});
AssertThrows: function(stExpected, fn)
	{
	try
		{
		fn(this);
		}
	catch (e)
		{
		this.AssertException(e, stExpected);
		return;
		}
    this.Assert(false, "Missing expected Exception: " + stExpected);
	},

// Assert expected and caught exceptions
// If stExpected != undefined, e.name or e.message must contain it
AssertException: function(e, stExpected)
    {
    if (e.name) e.name = e.name.toLowerCase();
    if (e.message) e.message = e.message.toLowerCase();
    if (stExpected) stExpected = stExpected.toLowerCase();
    this.Assert(!stExpected || e.name.indexOf(stExpected) != -1 ||
        e.message.indexOf(stExpected) != -1,
        "Exception: " + e.name + " (" + e.message + ")" +
        (stExpected ? " Expecting: " + stExpected : ""));
    this.cThrows++;
    },
    
// AsyncSequence - Run a sequence of asynchronous function calls
// Each fn(ut) must call ut.NextFn() to advance
// Last call to NextFn calls Async(false)
AsyncSequence: function(rgfn)
{
	this.rgfn = rgfn;
	this.ifn = 0;
	this.NextFn();
},

NextFn: function()
	{
	if (this.ifn >= this.rgfn.length)
		{
		this.Async(false);
		return;
		}
	this.rgfn[this.ifn++](this);
	}
};

// TestResult - a single result from the test

PF.TestResult = function (f, ut, stNote)
{
    this.f = f;
    this.ut = ut;
    this.stNote = stNote;
};

// ------------------------------------------------------------------------
// Test Suite - Holds, executes, and reports on a collection of unit tests.
// ------------------------------------------------------------------------

PF.TestSuite = function (stName)
{
    this.stName = stName;
    this.rgut = [];
    this.stOut = "";
};


PF.TestSuite.prototype = {
constructor: PF.TestSuite,
    cFailures: 0,
    iReport: -1,
    fStopFail: false,
    fTerminateAll: false,
    iutNext: 0,				// Will auto-disable any unit test less than iutNext (see SkipTo)

AddTest: function(stName, fn)
    {
    var ut = new PF.UnitTest(stName, fn);
    this.rgut.push(ut);
    
    // Global setting - stop all unit tests on first failure.
    if (this.fStopFail)
    	ut.StopFail(true)

    return ut;  
    },
    
StopFail: function(f)
	{
	this.fStopFail = f;
	return this;
	},
	
SkipTo: function(iut)
	{
	// Tests displayed as one-based
	this.iutNext = iut-1;
	return this;
	},

// We support asynchronous tests - so we use a timer to kick off tests when the current one
// is complete.
Run: function()
    {
    // BUG: should this be Active(false) - since we do first iteration immediately?
    this.tmRun = new PF.Timer(this.RunNext.FnCallback(this), 100).Repeat().Active(true);

    this.iCur = 0;
    // Don't wait for timer - start right away.
    this.RunNext();
    },
    
RunNext: function()
    {
    if (this.iCur == this.rgut.length)
        return;

    this.tmRun.Active(false);
loop:
    while (this.iCur < this.rgut.length)
        {
        var ut = this.rgut[this.iCur];
        var state = ut.state;
        if (!ut.fEnable || this.fTerminateAll || this.iCur < this.iutNext)
            state = PF.UnitTest.states.completed;
        switch(state)
            {
        case PF.UnitTest.states.created:
            ut.Run();
            break;
        case PF.UnitTest.states.running:
            break loop;
        case PF.UnitTest.states.completed:
            this.iCur++;
            this.ReportWhenReady();
            // Skip all remaining tests on failure if StopFail
            if (this.fStopFail && ut.cErrors != ut.cErrorsExpected)
            	this.fTerminateAll = true;
            break;
            }
        }
    this.tmRun.Active(true);
    },

AllComplete: function()
    {
    return (this.iCur == this.rgut.length);
    },
    
DWOutputDiv: function()
    {
    PF.DW("<DIV style=\"font-family: Courier;border:1px solid red;\" id=\"divUnit\">Unit Test Output</DIV>");
    },

Out: function(st)
    {
    this.stOut += st;
    return this;
    },
    
OutRef: function(st, url)
    {
    if (!url)
        {
        this.Out(st);
        return;
        }
    if (this.divOut)
        this.Out("<A target=\"_blank\" href=\"" + url + "\">" + st + "</A>");
    else
        {
        if (st != url)
            this.Out(st + " (" + url + ")");
        else
            this.Out(st);
        }
    },

NL: function()
    {
    if (this.divOut)
        {
        this.divOut.appendChild(document.createElement("BR"));
        var txt = document.createElement("span");
        txt.innerHTML = this.stOut;
        this.divOut.appendChild(txt);
        }
    else if (typeof console != "undefined")
        console.log(this.stOut);
    else
        alert(this.stOut);
    this.stOut = "";
    return this;
    },

Report: function()
    {
    this.divOut = this.divOut || document.getElementById("divUnit");    
    this.cFailures = 0;
    this.iReport = 0;
    this.ReportWhenReady();
    },

ReportWhenReady: function()
    {
    // Reporting not enabled
    if (this.iReport == -1)
        return;
    while (this.iReport < this.iCur)
        this.ReportOne(this.iReport++);
    
    if (!this.AllComplete())
        return;

    this.ReportSummary();
    this.ReportOut();
    },

ReportOne: function(i)
    {
    var ut = this.rgut[i];
    this.Out((i+1) + ". ");

    switch (ut.state)
        {
    case PF.UnitTest.states.created:
        this.Out("N/A");
        break;
    case PF.UnitTest.states.running:
        if (ut.cAsync > 0)
            this.Out("RUNNING");
        else
            {
            this.Out("INCOMPLETE");
            }
        this.cFailures++;
        break;
    case PF.UnitTest.states.completed:
        if (ut.cErrors == ut.cErrorsExpected &&
            (ut.cTestsExpected == undefined || ut.cTestsExpected == ut.cAsserts))
            this.Out("PASS");
        else
            {
            this.Out("FAIL");
            this.cFailures++;
            }
        break;
        }

    this.Out(" [");
    this.OutRef(ut.stName, ut.urlRef);
    this.Out("] ");

    if (ut.state != PF.UnitTest.states.created)
        {
        this.Out(ut.cErrors + " errors " + "out of " + ut.cAsserts + " tests");
        if (ut.cTestsExpected && ut.cTestsExpected != ut.cAsserts)
            this.Out(" (" + ut.cTestsExpected + " expected)");
        }
    this.NL();

    for (var j = 0; j < ut.rgres.length; j++)
        {
        var res = ut.rgres[j];
        if (!res.f)
            this.Out("Failed: " + res.stNote).NL();
        }
    },
    
ReportSummary: function()
    {
    if (this.cFailures == 0)
        this.Out("Summary: All (" + this.rgut.length + ") tests pass.").NL();
    else        
        this.Out("Summary: " + this.cFailures + " failures out of " + this.rgut.length + " tests.").NL();
    },

// Report results to master unit test, if any.
ReportOut: function()
    {
    if (!this.AllComplete())
        return;
    if (window.opener && window.opener.MasterTest)
        {
        var iUnit = parseInt(window.name.replace(/^Unit_/, ""));
        window.opener.MasterTest(iUnit, this.cFailures, this.rgut.length);
        }
    },
    
AddSubTest: function(stPath)
    {
    var ut = this.AddTest(stPath, this.RunSubTest.FnCallback(this)).Async(true).Reference(stPath);
    ut.stPath = stPath;
    ut.iUnit = this.rgut.length-1;
    return ut;
    },
    
RunSubTest: function(ut)
    {
    var stName = "Unit_" + ut.iUnit;
    // Ensure unique name even if multi-level of master-child tests.
    if (window.name)
        stName += " from " + window.name;
    ut.win = window.open(ut.stPath, "Unit_" + ut.iUnit);
    if (window.MasterTest == undefined)
        window.MasterTest = this.MasterTest.FnCallback(this);
    },
    
MasterTest: function(iUnit, cErrors, cTests)
    {
    var ut = this.rgut[iUnit];
    ut.cErrors = cErrors;
    ut.cAsserts = cTests;
    ut.Async(false);
    if (ut.cErrors == ut.cErrorsExpected)
        ut.win.close();
    }
};
