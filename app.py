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
                        scope="playlist-modify-public")

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

@app.route('/create_playlist', methods=['GET', 'POST'])
def create_playlist():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')

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

            return render_template('select_songs.html', search_results=search_results, playlist_name=playlist_name, setlist_url=setlist_url)

        except Exception as e:
            print(f"Error during playlist creation: {e}")
            return f"An error occurred: {e}", 500

    # Handle the GET request by rendering the form to create a playlist
    return render_template('create_playlist.html')


# Function to clean song titles by removing extra spaces, unwanted text, and anything in parentheses
def clean_song_title(title):
    # Remove anything within parentheses and parentheses themselves
    title = re.sub(r'\([^)]*\)', '', title)
    # Remove "Play Video" and extra spaces
    return ' '.join(title.replace('Play Video', '').split()).strip()


@app.route('/finalize_playlist', methods=['POST'])
def finalize_playlist():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')

    sp = Spotify(auth=token_info['access_token'])
    playlist_name = request.form['playlist_name']

    # Collect all selected track URIs
    selected_track_uris = request.form.getlist('selected_tracks')  # getlist() to handle multiple selected tracks

    # Create Spotify playlist
    user_id = sp.current_user()['id']
    playlist = sp.user_playlist_create(user_id, name=playlist_name, public=True)
    playlist_id = playlist['id']

    # Add selected tracks to the playlist
    if selected_track_uris:
        sp.playlist_add_items(playlist_id, selected_track_uris)
        return f"Playlist '{playlist_name}' created with selected songs!"
    else:
        return "No tracks were selected to add to the playlist."



# Helper function to scrape Setlist.fm and clean song titles
def get_setlist_songs_and_artist(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    artist_name = soup.find('meta', {'name': 'description'}).get('content').split(' Setlist')[0].replace('Get the ', '').strip()
    raw_song_titles = [song.get_text() for song in soup.find_all('li', class_='setlistParts song')]
    song_titles = [clean_song_title(song) for song in raw_song_titles]
    return artist_name, song_titles

# Function to search for songs on Spotify and return track URIs
def search_spotify_tracks(sp, song_titles, artist_name):
    track_uris = []
    for song in song_titles:
        query = f"{song} artist:{artist_name}"
        print(f"Searching for: {query}")  # Debugging search query
        results = sp.search(q=query, type='track', limit=5)  # Searching for up to 5 matches
        if results['tracks']['items']:
            track_uris.append(results['tracks']['items'][0]['uri'])
        else:
            print(f"No match found for {song} by {artist_name}")
    return track_uris

if __name__ == '__main__':
    app.run(debug=True)
