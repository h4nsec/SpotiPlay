import os
from flask import Flask, request, redirect, session, render_template
from spotipy import SpotifyOAuth, Spotify
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')
app.config['SESSION_COOKIE_NAME'] = 'spotify-session'

# Spotify API setup
SPOTIPY_CLIENT_ID = os.environ.get('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.environ.get('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = "https://spotiplay-3n9t.onrender.com/callback"

sp_oauth = SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID,
                        client_secret=SPOTIPY_CLIENT_SECRET,
                        redirect_uri=SPOTIPY_REDIRECT_URI,
                        scope="playlist-read-private playlist-modify-public")

@app.route('/')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return render_template('login.html', auth_url=auth_url)

@app.route('/callback')
def callback():
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect('/create_playlist')

# View for creating a new playlist
@app.route('/create_playlist', methods=['GET', 'POST'])
def create_playlist_view():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/login')

    sp = Spotify(auth=token_info['access_token'])

    if request.method == 'POST':
        playlist_name = request.form['playlist_name']
        setlist_url = request.form['setlist_url']

        try:
            artist_name, song_titles = get_setlist_songs_and_artist(setlist_url)

            if not song_titles:
                return "No songs found in the setlist.", 400

            # Search for Spotify tracks
            search_results = {}
            for song in song_titles:
                search_results[song] = sp.search(q=f"{song} artist:{artist_name}", type='track', limit=5)['tracks']['items']

            return render_template('select_songs.html', search_results=search_results, playlist_name=playlist_name)

        except Exception as e:
            print(f"Error during playlist creation: {e}")
            return f"An error occurred: {e}", 500

    return render_template('create_playlist.html')

# View for updating an existing playlist
@app.route('/update_playlist', methods=['GET', 'POST'])
def update_playlist_view():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/login')

    sp = Spotify(auth=token_info['access_token'])

    if request.method == 'POST':
        playlist_id = request.form['playlist_id']
        setlist_url = request.form['setlist_url_update']

        try:
            artist_name, song_titles = get_setlist_songs_and_artist(setlist_url)

            if not song_titles:
                return "No songs found in the setlist.", 400

            # Search for Spotify tracks
            search_results = {}
            for song in song_titles:
                search_results[song] = sp.search(q=f"{song} artist:{artist_name}", type='track', limit=5)['tracks']['items']

            return render_template('select_songs.html', search_results=search_results, playlist_id=playlist_id)

        except Exception as e:
            print(f"Error during playlist update: {e}")
            return f"An error occurred: {e}", 500

    # Fetch existing playlists
    try:
        playlists = sp.current_user_playlists(limit=10)['items']
    except Exception as e:
        print(f"Error fetching playlists: {e}")
        playlists = []
    
    return render_template('update_playlist.html', playlists=playlists)

# Finalize playlist creation
@app.route('/finalize_playlist', methods=['POST'])
def finalize_playlist():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')

    sp = Spotify(auth=token_info['access_token'])

    # Determine if it's an update or a new playlist creation
    playlist_id = request.form.get('playlist_id', None)
    playlist_name = request.form.get('playlist_name', None)
    selected_track_uris = request.form.getlist('selected_tracks')

    if not selected_track_uris:
        return "No tracks were selected."

    # If updating an existing playlist
    if playlist_id:
        sp.playlist_add_items(playlist_id, selected_track_uris)
        return f"Playlist updated with selected songs!"
    # If creating a new playlist
    else:
        user_id = sp.current_user()['id']
        playlist = sp.user_playlist_create(user_id, name=playlist_name, public=True)
        sp.playlist_add_items(playlist['id'], selected_track_uris)
        return f"New playlist '{playlist_name}' created with selected songs!"

# Helper functions to clean up song titles and fetch song details from Setlist.fm
def clean_song_title(title):
    title = re.sub(r'\([^)]*\)', '', title)
    return ' '.join(title.replace('Play Video', '').split()).strip()

def get_setlist_songs_and_artist(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    artist_name = soup.find('meta', {'name': 'description'}).get('content').split(' Setlist')[0].replace('Get the ', '').strip()
    raw_song_titles = [song.get_text() for song in soup.find_all('li', class_='setlistParts song')]
    song_titles = [clean_song_title(song) for song in raw_song_titles]
    return artist_name, song_titles

@app.before_request
def refresh_token():
    token_info = session.get('token_info', None)
    if token_info:
        if sp_oauth.is_token_expired(token_info):
            token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
            session['token_info'] = token_info

if __name__ == '__main__':
    app.run(debug=True)
