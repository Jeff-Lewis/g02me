from google.appengine.ext import db
from google.appengine.api import users, memcache
from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect

from util import *
from models import *

import logging

def Home(req):
    if IsJSON():
        return HttpJSON(req, Map.TopJSON())
    AddToResponse({
       'pages': Map.TopPages(),
       'total_pages': Globals.IdGet(settings.sMapName, settings.idMapBase) -
            settings.idMapBase + 1 + settings.cPagesExtra
                   })
    return render_to_response('home.html', FinalResponse())

def CatchAll(req):
    raise Error("Page not found", "Fail/NotFound")

def MakeAlias(req):
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

regUsername = re.compile(r"^[a-zA-Z0-9_\.\-]{1,20}$")

def SetUsername(req):
    TrySetUsername(req, req.REQUEST.get('username', ''), True)
    if IsJSON():
        return HttpJSON(req, obj={'username':local.requser.username})
    return HttpResponseRedirect('/')

def TrySetUsername(req, sUsername, fSetEmpty=False):
    if sUsername == '' and not fSetEmpty:
        return;
    
    if sUsername == local.requser.username:
        return

    if sUsername != '' and not regUsername.match(sUsername):
        raise Error("Invalid Nickname: %s" % sUsername)
    if not req.GET.get('force', False) and Comment.FUsernameUsed(sUsername):
        raise Error("Username (%s) already in use" % sUsername, 'Fail/Used')
    local.requser.username = sUsername

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
        
        TrySetUsername(req, parts['username'])
        
        map.AddComment(username=local.requser.username, comment=parts['comment'], tags=parts['tags'])

    if IsJSON():
        return HttpJSON(req, obj=map.JSON())
    return HttpResponseRedirect("/info/%s" % map.GetId())
    

def Head(req, id):
    # http://go2.me/info/N
    map = Map.Lookup(id)
    if map == None:
        RaiseNotFound(id)
    map.Viewed()
    if IsJSON():
        return HttpJSON(req, obj=map.JSON())
    AddToResponse({'map': map, 'TopTags':map.TopTags()})
    return render_to_response('head.html', FinalResponse())

def FrameSet(req, id):
    # http://go.2me/N
    map = Map.Lookup(id)
    if map == None:
        RaiseNotFound(id)
    if IsJSON():
        map.Viewed()
        return HttpJSON(req, obj=map.JSON())
    AddToResponse({'map':map})
    return render_to_response('mapped.html', FinalResponse())

def UserView(req, username):
    if IsJSON():
        return HttpJSON(req, obj=Comment.ForUserJSON(username))
    comments = Comment.ForUser(username)
    AddToResponse({'usernamePage':username, 'comments':comments})
    return render_to_response('user.html', FinalResponse())

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
          
