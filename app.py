import os
from flask import Flask, request, redirect, session, render_template
from spotipy import SpotifyOAuth, Spotify
import requests
from bs4 import BeautifulSoup



app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')  # Use a secret key from environment
app.config['SESSION_COOKIE_NAME'] = 'spotify-session'

# Spotify API setup
SPOTIPY_CLIENT_ID = os.environ.get('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.environ.get('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = os.environ.get('SPOTIPY_REDIRECT_URI')

sp_oauth = SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID,
                        client_secret=SPOTIPY_CLIENT_SECRET,
                        redirect_uri=SPOTIPY_REDIRECT_URI,
                        scope="playlist-modify-public")
@app.route('/')
def index():
    auth_url = sp_oauth.get_authorize_url()
    return render_template('index.html', auth_url=auth_url)

@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect('/dashboard')

@app.route('/dashboard')
def dashboard():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')
    
    sp = Spotify(auth=token_info['access_token'])
    user_profile = sp.current_user()
    
    return render_template('dashboard.html', user=user_profile)

# Endpoint to create a new playlist
@app.route('/create_playlist', methods=['POST'])
def create_playlist():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/login')

    sp = Spotify(auth=token_info['access_token'])
    playlist_name = request.form['playlist_name']
    setlist_url = request.form['setlist_url']
    
    # Process the Setlist.fm URL to get songs
    artist_name, song_titles = get_setlist_songs_and_artist(setlist_url)
    
    # Create Spotify playlist
    user_id = sp.current_user()['id']
    playlist = sp.user_playlist_create(user_id, name=playlist_name, public=True)
    playlist_id = playlist['id']

    # Add tracks to the playlist
    track_uris = search_spotify_tracks(sp, song_titles, artist_name)
    sp.playlist_add_items(playlist_id, track_uris)
    
    return f"Playlist '{playlist_name}' created!"

# Helper functions to scrape Setlist.fm and search songs
def get_setlist_songs_and_artist(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    artist_name = soup.find('meta', {'name': 'description'}).get('content').split(' Setlist')[0].strip()
    song_titles = [song.get_text().strip() for song in soup.find_all('li', class_='setlistParts song')]
    return artist_name, song_titles

def search_spotify_tracks(sp, song_titles, artist_name):
    track_uris = []
    for song in song_titles:
        query = f"{song} artist:{artist_name}"
        results = sp.search(q=query, type='track', limit=1)
        if results['tracks']['items']:
            track_uris.append(results['tracks']['items'][0]['uri'])
    return track_uris

if __name__ == '__main__':
    app.run(debug=True)
