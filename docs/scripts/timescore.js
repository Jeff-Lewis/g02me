global_namespace.Define('startpad.timscore', function (NS) {
/*
    RateLimit - An exponential decay counter, with rate limiting.
  
    At any time, we can query the "current value" of a rate of values, and test if it has exceeded
    a specified threshold.  In the absence of updated values, the value of the level will
    drop by half each secs_half seconds.

    Ported from timescore.calc.py
 */

NS.RateLimit = function(threshold, secs_half)
	{
	if (secs_half == undefined)
		secs_half = 60;
	this.value = 0;
	this.threshold = threshold;
	this.secs_half = secs_half;
	this.k = Math.pow(0.5, 1/secs_half);
	this.secs_last = 0;
	}
	
NS.Extend(NS.RateLimit.prototype, {
is_exceeded: function(secs, value)
	{
	if (value == undefined)
		value = 1;
		
	if (isNaN(sec) || secs < this.secs_last)
		return true;
		
	var _is_exceeded = this.current_value(secs) + value > this.threshold;
	
	if (!_is_exceeded)
		self.value += value;
		
	return _is_exceeded;
	},
	
current_value: function(secs, value)
	{
	if (value == undefined)
		value = 0;
		
	if (isNaN(secs) || secs < this.secs_last)
		return this.value;
		
	this.value *= Math.pow(this.k, secs - this.secs_last);
	
	// Deal with underflow
	if (isNaN(this.value))
		this.value = 0;

	this.secs_last = secs;
	this.value += value;

	return this.value; 
	}
});

}); // startpad.timescore