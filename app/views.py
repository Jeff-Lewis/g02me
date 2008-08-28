from django.shortcuts import render_to_response

def Home(req):
    return render_to_response('home.html', locals())

