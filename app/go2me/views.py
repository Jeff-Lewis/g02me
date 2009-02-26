from google.appengine.ext import db
from google.appengine.api import users, memcache

from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect

from util import *
from models import Map, Comment, Globals
import profile

import logging

def Home(req):
    AddToResponse({
       'total_pages': Globals.IdGet(settings.sMapName, settings.idMapBase) -
            settings.idMapBase + 1 + settings.cPagesExtra,
       'pages': Map.TopPages(limit=30)
       })
    return render_to_response('home.html', FinalResponse())

def Popular(req):
    if IsJSON():
        return HttpJSON(req, Map.TopJSON())
    
    AddToResponse({
       'pages': Map.TopPages(),
       'total_pages': Globals.IdGet(settings.sMapName, settings.idMapBase) -
            settings.idMapBase + 1 + settings.cPagesExtra
       })
    return render_to_response('popular.html', FinalResponse())

def CatchAll(req):
    raise Error("Page not found", "Fail/NotFound")

def MakeAlias(req):
    if IsJSON():
        local.requser.Require('api')
    map = Map.FindOrCreateUrl(local.mpParams.get('url', ""), local.mpParams.get('title', ""))
    if IsJSON():
        return HttpJSON(req, obj=map.JSON())
    return HttpResponseRedirect("/%s" % map.GetId())

def Lookup(req):
    map = Map.FindUrl(req.GET.get('url', ""))
    if map is None:
        raise Error("No shortened url exists", "Fail/NotFound")
    if IsJSON():
        return HttpJSON(req, obj=map.JSON())
    return HttpResponseRedirect("/%s" % map.GetId())

def SetUsername(req):
    if not IsJSON():
        raise Error("Can only use API to set nickname.")
    
    local.requser.SetOpenUsername(req.REQUEST.get('username', ''), fForce=req.GET.get('force', False))

    if local.requser.profile is not None and local.requser.username != local.requser.profile.username:
        raise Error("Require Google Logout", 'Fail/Auth/Logout',
                    {'urlLogout': JSONLogoutURL()})

    return HttpJSON(req, {'username': local.requser.username})

def InitAPI(req):
    # Return an IP-specific API key to the client - 10 WPM
    sKey = '~'.join((local.ipAddress, '10'))
    return HttpJSON(req, obj={'apikey':SSign('apiIP', sKey)})

def Favorite(req):
    local.requser.Require('api', 'write', 'comment', 'user')
    if not IsJSON():
        raise Error("Can only use API to set as favorite.")

    id = local.mpParams.get('id', "").strip()
    
    map = Map.Lookup(id)
    if map == None:
        RaiseNotFound(id)
    
    map.AddComment(username=local.requser.username, comment='__fave')
    
    return HttpJSON(req, obj=map.JSON())

def DoComment(req, command=None):
    local.requser.Require('api', 'write', 'comment')
    
    if command == 'delete':
        delkey = local.mpParams.get('delkey', '').strip()
        try:
            cid = int(SGetSigned('dk', delkey))
        except:
            raise Error("Invalid comment deletion key: %s" % delkey)
        comment = Comment.get_by_id(int(cid))
        if comment is None:
            raise Error("Comment id=%d does not exists" % cid, 'Fail/NotFound')
        map = comment.map
        comment.Delete()
        
    if command is None:
        id = local.mpParams.get('id', "").strip()
        
        map = Map.Lookup(id)
        if map == None:
            RaiseNotFound(id)
        
        parts = Comment.Parse(local.mpParams.get('username', ''), local.mpParams.get('comment', ''))
        
        local.requser.SetOpenUsername(parts['username'], fSetEmpty=False, fForce=req.GET.get('force', False))
        
        map.AddComment(username=local.requser.username, comment=parts['comment'], tags=parts['tags'])

    if IsJSON():
        dateSince = local.mpParams.get('since', None)
        if dateSince:
            dateSince = DateFromISO(dateSince)
        return HttpJSON(req, obj=map.JSON(dateSince=dateSince))
    return HttpResponseRedirect("/info/%s" % map.GetId())
    
def HeadRedirect(req, id):
    # http://go2.me/info/N
    sExtra = ''
    if req.META['QUERY_STRING']:
        sExtra = '?' + req.META['QUERY_STRING']
    return HttpResponsePermanentRedirect("/%s%s" % (id, sExtra))

def LinkPage(req, id):
    # http://go.2me/G
    map = Map.Lookup(id)
    if map == None:
        RaiseNotFound(id)
    if IsJSON():
        dateSince = local.mpParams.get('since', None)
        if dateSince:
            dateSince = DateFromISO(dateSince)
        
        return HttpJSON(req, obj=map.JSON(dateSince=dateSince))
    else:
        map.Viewed()
    AddToResponse({'map':map, 'TopTags':map.TopTags()})
    return render_to_response('mapped.html', FinalResponse())

def UserView(req, username):
    if IsJSON():
        return HttpJSON(req, obj=Comment.ForUserJSON(username))
    comments = Comment.ForUser(username)
    profileU = profile.Profile.Lookup(username)
    AddToResponse({'usernamePage':username, 'comments':comments, 'profilePage':profileU})
    return render_to_response('user.html', FinalResponse())

def UserProfile(req):
    local.requser.Require('user')
    if local.req.method == 'POST':
        local.requser.Require('post')
        profileForm = local.mpParams.copy()
        if local.requser.profile.SetForm(profileForm):
            return HttpResponseRedirect('/profile/#saved')
    else:
        profileForm = local.requser.profile.GetForm()

    AddToResponse({'profileForm':profileForm})
    return render_to_response('profile.html', FinalResponse())

def UserPicture(req, username, size):
    try:
        profileT = profile.Profile.Lookup(username)
        img = getattr(profileT, 'img_%s' % size)
        if img is None:
            raise Exception()
        resp = HttpResponse(img, mimetype="image/png")
    except:
        return HttpResponseRedirect('/images/picture_%s.png' % size)
    return resp


def TagView(req, tag):
    if IsJSON():
        return HttpJSON(req, Map.TopJSON(tag=tag))
    AddToResponse({'tag':tag, 'host':local.stHost, 'pages':Map.TopPages(tag=tag)})
    return render_to_response('tag.html', FinalResponse())

def Admin(req, command=None):
    local.requser.Require('admin')
    
    # BUG - Add CSRF required field
    if command:
        logging.info("admin command: %s" % command)
        local.requser.Require('api')

        if command == 'clean-broken':
            scores = Map.ss.Broken()
            logging.info("Removing %d broken scores" % len(scores))
            for score in scores:
                score.delete()
                
        if command == 'clean-comments':
            comments = Comment.BadComments()
            logging.info("Removing %d empty comments" % len(comments))
            for comment in comments:
                comment.Delete()
                
        if command == 'clean-broken-comments':
            comments = Comment.Broken()
            logging.info("Removing %d broken comments" % len(comments))
            for comment in comments:
                comment.Delete()
                
        if command == 'fix-tag-counts':
            maps = Map.FindBadTagCounts()
            logging.info("Fixing %d bad tag counts" % len(maps))
            Map.FixTagCounts(maps)
            
        if command == 'fix-missing-creators':
            comments = Comment.MissingCreator()
            logging.info("Fixing %d missing creators" % len(comments))
            Comment.FixMissingCreators(comments)
            
        if command == 'flush-memcache':
            memcache.flush_all()
            
        if command == 'create-api-key':
            logging.info('CAK')
            key = '~'.join((local.mpParams['dev'], local.mpParams['rate'], local.mpParams['exp']))
            raise Error('Signed API key: %s' % SSign('api', key), 'OK')
        
        if command == 'ban-id':
            try:
                map = Map.Lookup(local.mpParams['id'])
                map.Ban(local.mpParams['fBan'] == 'true')
            except:
                raise Error("Can't ban id: %s" % local.mpParams['id'])

        if IsJSON():
            return HttpJSON(req, {})
        return HttpResponseRedirect("/admin/")

    try:
        ms = memcache.get_stats()
        mpMem = [{'key':key, 'value':ms[key]} for key in ms]
    except:
        mpMem = [{'key':'message', 'value':'memcache get_stats() failure!'}]

    AddToResponse(
          {
           'logout':users.create_logout_url(req.get_full_path()),
           #'Broken':Map.ss.Broken(),
           #'EmptyComments':Comment.EmptyComments(),
           #'BrokenComments':Comment.Broken(),
           #'BadCounts':Map.FindBadTagCounts(),
           #'MissingCreator':Comment.MissingCreator(),
           'MemCache': mpMem
           })
    return render_to_response('admin.html', FinalResponse())
          
