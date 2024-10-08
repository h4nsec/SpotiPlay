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


# Login route
@app.route('/')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return render_template('login.html', auth_url=auth_url)


# Callback after Spotify login
@app.route('/callback')
def callback():
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect('/create_or_update')


# Create or update a playlist
@app.route('/create_or_update', methods=['GET', 'POST'])
def create_or_update_playlist():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')

    sp = Spotify(auth=token_info['access_token'])

    if request.method == 'POST':
        action = request.form.get('action')  # new or update
        setlist_url = request.form['setlist_url']

        if action == 'new':
            playlist_name = request.form['playlist_name']
            return handle_setlist(sp, setlist_url, playlist_name=playlist_name)
        elif action == 'update':
            playlist_id = request.form['playlist_id']
            return handle_setlist(sp, setlist_url, playlist_id=playlist_id)
    else:
        playlists = sp.current_user_playlists(limit=10)['items']
        return render_template('create_or_update.html', playlists=playlists)


def handle_setlist(sp, setlist_url, playlist_name=None, playlist_id=None):
    """Process setlist URL and allow user to confirm track selection."""
    try:
        artist_name, song_titles = get_setlist_songs_and_artist(setlist_url)
        if not song_titles:
            return "No songs found in the setlist.", 400

        search_results = {}
        for song in song_titles:
            search_results[song] = sp.search(q=f"{song} artist:{artist_name}", type='track', limit=5)['tracks']['items']

        return render_template('select_songs.html', search_results=search_results, playlist_name=playlist_name, playlist_id=playlist_id)
    except Exception as e:
        print(f"Error: {e}")
        return f"An error occurred: {e}", 500


# Finalize adding songs to playlist (create or update)
@app.route('/finalize_playlist', methods=['POST'])
def finalize_playlist():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')

    sp = Spotify(auth=token_info['access_token'])
    playlist_name = request.form.get('playlist_name')
    playlist_id = request.form.get('playlist_id')
    selected_tracks = request.form.getlist('selected_tracks')

    if not selected_tracks:
        return "No tracks were selected to add to the playlist."

    if playlist_id:
        # Update an existing playlist
        sp.playlist_add_items(playlist_id, selected_tracks)
        return f"Playlist updated with selected songs!"
    else:
        # Create a new playlist
        user_id = sp.current_user()['id']
        playlist = sp.user_playlist_create(user_id, name=playlist_name, public=True)
        sp.playlist_add_items(playlist['id'], selected_tracks)
        return f"Playlist '{playlist_name}' created with selected songs!"


# Helper function to scrape Setlist.fm and clean song titles
def get_setlist_songs_and_artist(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    artist_name = soup.find('meta', {'name': 'description'}).get('content').split(' Setlist')[0].replace('Get the ', '').strip()
    raw_song_titles = [song.get_text() for song in soup.find_all('li', class_='setlistParts song')]
    song_titles = [clean_song_title(song) for song in raw_song_titles]
    return artist_name, song_titles


# Function to clean song titles by removing extra spaces, unwanted text, and anything in parentheses
def clean_song_title(title):
    title = re.sub(r'\([^)]*\)', '', title)
    return ' '.join(title.replace('Play Video', '').split()).strip()


# Function to refresh token if expired
@app.before_request
def refresh_token():
    token_info = session.get('token_info', None)
    if token_info and sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['token_info'] = token_info


if __name__ == '__main__':
    app.run(debug=True)
