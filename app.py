# IMPORTS
import os
from googleapiclient.discovery import build
import google_auth_oauthlib.flow
import google.oauth2.credentials
import flask
import requests
import config
import threading
from requests_oauthlib import OAuth1Session

# VARIABLES GLOBALES
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
app = flask.Flask(__name__)
app.secret_key = '123'
CLIENT_SECRETS_FILE = 'client_secret.json'
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
'https://www.googleapis.com/auth/gmail.labels', 'https://www.googleapis.com/auth/gmail.modify']

# RUTAS
@app.route('/')
def home():
  return 'Home page'


@app.route('/profile')
def profile():
  gmail_status = 'Declined'
  trello_status = 'Declined'
  username = ''

  if 'credentials' in flask.session:
    gmail_status = 'Accepted'

  if 'user_token_trello' in flask.session:
    trello_status = 'Accepted'
    token = flask.session['user_token_trello']
    username = requests.get(f'https://api.trello.com/1/members/me?key={config.API_KEY}&token={token}').json()['fullName']

  if 'credentials' in flask.session and 'user_token_trello' in flask.session:
    credentials = google.oauth2.credentials.Credentials(**flask.session['credentials'])
    service = build('gmail', 'v1', credentials=credentials)
    gmail_adress = service.users().getProfile(userId='me').execute()
    flask.session['gmail_adress'] = dict(gmail_adress)['emailAddress']

    @flask.copy_current_request_context
    def trelloBot():
      try:
            token = flask.session['user_token_trello']
            email_list = service.users().messages().list(userId='me', maxResults=1).execute()
            value = 1
            while value == 1:
              updated_list = service.users().messages().list(userId='me', maxResults=1).execute()
              last_mail = updated_list['messages']
              if last_mail != email_list['messages']:
                email_list = updated_list
                mail_id = last_mail[0]['id']
                if mail_id:
                  message = service.users().messages().get(userId='me', id=mail_id).execute()
                  if message and 'INBOX' in message['labelIds']:
                    message_headers = message['payload']['headers']
                    for item in message_headers:
                        if item['name'] == 'Subject':
                            if '[TRELLO BOT]' in item['value']:
                                print('Orden recibida...')
                                subject = item['value'].replace('[TRELLO BOT] ', '')
                                boards = requests.get(f'https://api.trello.com/1/members/me/boards?key={config.API_KEY}&token={token}').json()

                                for board in boards:
                                  id = board['id']
                                  board_lists = requests.get(f'https://api.trello.com/1/boards/{id}/lists?key={config.API_KEY}&token={token}').json()
                                  id_list = board_lists[0]['id']
                                  create_card = requests.post(f'https://api.trello.com/1/cards?idList={id_list}&key={config.API_KEY}&token={token}', {'name': subject, 'desc': message['snippet']})
                                
                                # Marca el correo como leído.
                                remove_label = service.users().messages().modify(userId='me', id=mail_id, body={"removeLabelIds": ['UNREAD']}).execute()

      except Exception as e:
          print(e)
    
    x = threading.Thread(target=trelloBot, args=())
    x.start()
  return flask.render_template('profile.html', trello_status=trello_status, gmail_status=gmail_status, username=username)


@app.route('/logout')
def logOut():
  flask.session.clear()
  return flask.redirect(flask.url_for('profile'))


# PROTOCOLO OAUTH2 PARA AUTORIZACION DE GOOGLE

@app.route('/authorize')
def authorize():
  if 'credentials' in flask.session:
    return flask.redirect('/profile')
  flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES)
  # Donde me manda luego de autorizar
  flow.redirect_uri = flask.url_for('oauth2callback', _external=True, _scheme='http')
  authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')

  flask.session['state'] = state

  return flask.redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
  state = flask.session['state']
  flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
  flow.redirect_uri = flask.url_for('oauth2callback', _external=True, _scheme='http')

  authorization_response = flask.request.url
  flow.fetch_token(authorization_response=authorization_response)

  credentials = flow.credentials
  flask.session['credentials'] = {
    'token': credentials.token,
    'refresh_token': credentials.refresh_token,
    'token_uri': credentials.token_uri,
    'client_id': credentials.client_id,
    'client_secret': credentials.client_secret,
    'scopes': credentials.scopes
  }

  return flask.redirect('/profile')


# PROTOCOLO OAUTH1 PARA AUTORIZACIÓN DE TRELLO

@app.route('/trelloAuth')
def auth():

  if 'user_token_trello' in flask.session:
    flask.redirect('/profile')

  request_token_url = 'https://trello.com/1/OAuthGetRequestToken'
  base_authorization_url = 'https://trello.com/1/OAuthAuthorizeToken'
  oauth = OAuth1Session(client_key=config.API_KEY, client_secret=config.API_SECRET)
  fetch_response = oauth.fetch_request_token(request_token_url)
  flask.session['resource_owner_key'] = fetch_response.get('oauth_token')
  flask.session['resource_owner_secret'] = fetch_response.get('oauth_token_secret')
  authorization_url = oauth.authorization_url(base_authorization_url)

  return flask.redirect(authorization_url+'&return_url=http://127.0.0.1:5000/trelloCallback&scope=read,write&expiration=never&name=FedeSuperApp')


@app.route('/trelloCallback')
def callback():
  access_token_url = 'https://trello.com/1/OAuthGetAccessToken'
  oauth_token = flask.request.args.get('oauth_token')
  oauth_verifier = flask.request.args.get('oauth_verifier')
  oauth = OAuth1Session(client_key=config.API_KEY, client_secret=config.API_SECRET, resource_owner_key=flask.session['resource_owner_key'], resource_owner_secret=flask.session['resource_owner_secret'], verifier=oauth_verifier)
  oauth_tokens = oauth.fetch_access_token(access_token_url)

  flask.session['user_token_trello'] = oauth_tokens.get('oauth_token')
  resource_owner_secret = oauth_tokens.get('oauth_token_secret')

  return flask.redirect(flask.url_for('profile'))



# INICIO DE FLASK

if __name__ == '__main__':
  app.run(debug=True)