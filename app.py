import streamlit as st
import pandas as pd
import zipfile
import json
from datetime import timedelta, datetime
import os
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Spotify Analytics", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS for the specified styling
st.markdown("""
<style>
    /* Hide default sidebar */
    [data-testid="stSidebar"] {
        display: none;
    }
    
    /* Main container adjustments */
    .main .block-container {
        padding-top: 2rem;
        max-width: 100%;
    }
    
    /* Background color */
    .stApp {
        background-color: #1A0033;
    }
    
    /* Headings in orange */
    h1, h2, h3, h4, h5, h6 {
        color: #F97316 !important;
    }
    
    /* Hero title */
    .hero-title {
        font-size: 4rem;
        font-weight: bold;
        color: #F97316;
        margin-bottom: 1rem;
    }
    
    /* Hero subtitle */
    .hero-subtitle {
        font-size: 1.25rem;
        color: #ffffff;
        margin-bottom: 2rem;
    }
    
    /* Text color */
    .stMarkdown, .stText, p, span, div {
        color: #ffffff !important;
    }
    
    /* Button and dropdown styling */
    .stButton > button {
        background-color: #0D001A !important;
        color: #ffffff !important;
        border: 1px solid #2C0058 !important;
    }
    
    .stSelectbox > div > div {
        background-color: #0D001A !important;
        color: #ffffff !important;
    }
    
    .stNumberInput > div > div > input {
        background-color: #0D001A !important;
        color: #ffffff !important;
    }
    
    /* Table styling */
    .stDataFrame table {
        border-collapse: collapse;
    }
    
    .stDataFrame table th {
        background-color: #1E2136 !important;
        color: #ffffff !important;
        font-weight: bold;
        text-transform: uppercase;
        border: none;
        border-bottom: 1px solid #ffffff;
    }
    
    .stDataFrame table td {
        border: none;
        border-bottom: 1px solid #ffffff;
    }
    
    .stDataFrame table tr:nth-child(even) {
        background-color: #2C0058 !important;
    }
    
    /* Progress bar styling */
    .stProgress > div > div > div > div {
        background-color: #F97316 !important;
    }
    
    /* File uploader styling */
    .stFileUploader > section {
        background-color: #0D001A !important;
        border: 1px solid #2C0058 !important;
    }
    
    .stFileUploader > section > div {
        background-color: #0D001A !important;
    }
    
    /* Download button styling */
    .stDownloadButton > button {
        background-color: #0D001A !important;
        color: #ffffff !important;
        border: 1px solid #2C0058 !important;
    }
</style>
""", unsafe_allow_html=True)

def load_default_data():
    """Load default data from local files"""
    try:
        if os.path.exists('Spotify Extended Streaming History.zip'):
            with zipfile.ZipFile('Spotify Extended Streaming History.zip', 'r') as zip_ref:
                all_data = []
                for file_name in zip_ref.namelist():
                    if file_name.endswith('.json'):
                        with zip_ref.open(file_name) as json_file:
                            data = json.load(json_file)
                            all_data.extend(data)
                return pd.DataFrame(all_data) if all_data else None
    except Exception as e:
        st.error(f"Error loading default data: {str(e)}")
    return None

def load_default_playlists():
    """Load default playlist data from local file"""
    try:
        if os.path.exists('Playlist1.json'):
            try:
                with open('Playlist1.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
            except UnicodeDecodeError:
                with open('Playlist1.json', 'r', encoding='latin-1') as f:
                    return json.load(f)
    except Exception as e:
        st.error(f"Error loading default playlists: {str(e)}")
    return None

def process_spotify_data(uploaded_files):
    all_data = []
    for uploaded_file in uploaded_files:
        if uploaded_file.name.endswith('.zip'):
            with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
                for file_name in zip_ref.namelist():
                    if file_name.endswith('.json'):
                        with zip_ref.open(file_name) as json_file:
                            data = json.load(json_file)
                            all_data.extend(data)
        else:
            data = json.load(uploaded_file)
            all_data.extend(data)
    
    return pd.DataFrame(all_data) if all_data else None

def process_playlist_data(uploaded_file):
    try:
        data = json.load(uploaded_file)
        return data
    except Exception as e:
        st.error(f"Error loading playlist file: {str(e)}")
        return None

def calculate_peak_fixation(song_df):
    """Calculate peak fixation using rolling 30-day windows - the core analysis feature"""
    song_df = song_df.sort_values('date')
    dates = song_df['date'].unique()
    
    max_fixation = 0
    peak_date = None
    best_window_stats = {}
    
    for end_date in dates:
        start_date = end_date - timedelta(days=30)
        window_df = song_df[(song_df['date'] >= start_date) & (song_df['date'] <= end_date)]
        
        if len(window_df) == 0:
            continue
            
        real_plays = (window_df['ms_played'] >= 25000).sum()
        if real_plays < 2:
            continue
            
        total_plays = len(window_df)
        selections = (window_df['reason_start'] == 'clickrow').sum()
        skips = (window_df['ms_played'] < 25000).sum()
        
        fixation = float(real_plays) + (float(selections) / float(total_plays))
        
        if fixation > max_fixation:
            max_fixation = fixation
            peak_date = end_date
            best_window_stats = {
                'real_plays': int(real_plays),
                'selections': int(selections),
                'skips': int(skips),
                'total_plays': int(total_plays)
            }
    
    return max_fixation, peak_date, best_window_stats

def calculate_monthly_peak_fixations(song_df):
    """Calculate peak fixation for each month using rolling windows"""
    song_df = song_df.copy()  # Work with a copy to avoid warnings
    song_df = song_df.sort_values('date')
    song_df['month'] = pd.to_datetime(song_df['ts'], utc=True).dt.to_period('M')
    
    monthly_peaks = {}
    
    for month in song_df['month'].unique():
        month_data = song_df[song_df['month'] == month]
        if len(month_data) == 0:
            continue
            
        # For this month, calculate the best 30-day window that overlaps with this month
        month_start = month.start_time.date()
        month_end = month.end_time.date()
        
        max_fixation = 0
        
        for end_date in month_data['date'].unique():
            start_date = end_date - timedelta(days=30)
            # Only consider windows that overlap with this month
            if start_date <= month_end and end_date >= month_start:
                window_df = song_df[(song_df['date'] >= start_date) & (song_df['date'] <= end_date)]
                
                if len(window_df) == 0:
                    continue
                    
                real_plays = (window_df['ms_played'] >= 25000).sum()
                if real_plays < 2:
                    continue
                    
                total_plays = len(window_df)
                selections = (window_df['reason_start'] == 'clickrow').sum()
                
                fixation = float(real_plays) + (float(selections) / float(total_plays))
                max_fixation = max(max_fixation, fixation)
        
        monthly_peaks[str(month)] = max_fixation
    
    return monthly_peaks

def calculate_fixation_for_period(song_df, start_date, end_date):
    """Calculate fixation for a specific period"""
    period_df = song_df[(song_df['date'] >= start_date) & (song_df['date'] <= end_date)]
    if len(period_df) == 0:
        return 0
    
    real_plays = (period_df['ms_played'] >= 25000).sum()
    if real_plays < 2:
        return 0
    
    total_plays = len(period_df)
    selections = (period_df['reason_start'] == 'clickrow').sum()
    
    return float(real_plays) + (float(selections) / float(total_plays))

# Initialize session state
if 'data' not in st.session_state:
    st.session_state.data = None
if 'playlists' not in st.session_state:
    st.session_state.playlists = None
if 'filtered_songs' not in st.session_state:
    st.session_state.filtered_songs = set()
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'Dashboard'
if 'default_data_loaded' not in st.session_state:
    st.session_state.default_data_loaded = False
if 'playlist_view_states' not in st.session_state:
    st.session_state.playlist_view_states = {}
if 'filtered_playlists' not in st.session_state:
    st.session_state.filtered_playlists = set()

# Load default data on first run
if not st.session_state.default_data_loaded:
    with st.spinner("Loading default data..."):
        st.session_state.data = load_default_data()
        st.session_state.playlists = load_default_playlists()
        st.session_state.default_data_loaded = True

# Navigation
nav_col1, nav_col2, nav_col3, nav_col4, nav_col5, nav_spacer, nav_col6 = st.columns([1, 1, 1, 1, 1, 3, 1])

with nav_col1:
    if st.button("Dashboard", use_container_width=True):
        st.session_state.current_page = 'Dashboard'
with nav_col2:
    if st.button("Listening History", use_container_width=True):
        st.session_state.current_page = 'Listening History'
with nav_col3:
    if st.button("Playlists", use_container_width=True):
        st.session_state.current_page = 'Playlists'
with nav_col4:
    if st.button("Data Visualization", use_container_width=True):
        st.session_state.current_page = 'Data Visualization'
with nav_col6:
    if st.button("Import Data", use_container_width=True):
        st.session_state.current_page = 'Import Data'

st.divider()

# Page content based on navigation
if st.session_state.current_page == 'Dashboard':
    # Hero section
    st.markdown('<h1 class="hero-title">Your Music<br>Tells a Story</h1>', unsafe_allow_html=True)
    st.markdown('<p class="hero-subtitle">Transform your Spotify history into meaningful musical discoveries and insights.</p>', unsafe_allow_html=True)
    
    # Features section
    st.markdown("### FEATURES")
    st.markdown("## Everything you need to analyze your music")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### Detailed Analytics")
        st.write("Visualize your listening habits with interactive charts and graphs showing your top tracks, artists, and genres.")
    
    with col2:
        st.markdown("#### Time Filters")
        st.write("Filter your data by day, week, month, or custom date ranges to see how your tastes evolve over time.")
    
    with col3:
        st.markdown("#### Data Visualization")
        st.write("Interactive charts and pivot tables to analyze your music trends over time.")
    
    # Overview metrics if data is loaded
    if st.session_state.data is not None:
        st.divider()
        df = st.session_state.data.copy()
        df = df[df['master_metadata_track_name'].notna()].copy()
        df['date'] = pd.to_datetime(df['ts']).dt.date
        
        st.markdown("## Overview")
        
        # Metrics cards
        col1, col2, col3, col4 = st.columns(4)
        real_plays_count = (df['ms_played'] >= 25000).sum()
        col1.metric("Real Plays", f"{real_plays_count:,}")
        col2.metric("Unique Tracks", f"{df['master_metadata_track_name'].nunique():,}")
        col3.metric("Unique Artists", f"{df['master_metadata_album_artist_name'].nunique():,}")
        col4.metric("Hours", f"{df['ms_played'].sum() / (1000*60*60):,.0f}")
        
        # Top 10 Artists and Songs based on real plays
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Top 10 Artists")
            # Filter to real plays only, then count by artist
            real_plays_df = df[df['ms_played'] >= 25000]
            top_artists = real_plays_df['master_metadata_album_artist_name'].value_counts().head(10).reset_index()
            top_artists.columns = ['Artist', 'Real Plays']
            st.dataframe(top_artists, width='stretch', hide_index=True)
        
        with col2:
            st.markdown("### Top 10 Songs")
            # Filter to real plays only, then count by song
            top_songs = real_plays_df.groupby(['master_metadata_album_artist_name', 'master_metadata_track_name']).size().reset_index(name='Real Plays')
            top_songs = top_songs.sort_values('Real Plays', ascending=False).head(10)
            top_songs.columns = ['Artist', 'Track', 'Real Plays']
            st.dataframe(top_songs[['Track', 'Artist', 'Real Plays']], width='stretch', hide_index=True)
        
        # Monthly listening graph
        st.markdown("### Monthly Listening Activity")
        df_copy = df.copy()
        df_copy['month'] = pd.to_datetime(df_copy['ts'], utc=True).dt.to_period('M')
        monthly_data = df_copy.groupby('month').size().reset_index(name='plays')
        monthly_data['month'] = monthly_data['month'].astype(str)
        
        fig = px.bar(monthly_data, x='month', y='plays', title='Monthly Listening Activity')
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='white'
        )
        st.plotly_chart(fig, use_container_width=True)

elif st.session_state.current_page == 'Listening History':
    if st.session_state.data is None:
        st.warning("No data loaded. Please go to 'Import Data' to upload your Spotify data.")
    else:
        df = st.session_state.data.copy()
        df = df[df['master_metadata_track_name'].notna()].copy()
        df['date'] = pd.to_datetime(df['ts']).dt.date
        
        st.header("Listening History")
        
        # Tab controls
        tabs = st.tabs(["All Time", "Recent (30 days)", "Last Year"])
        
        with tabs[0]:
            st.subheader("All Time (Songs with at least 3 plays)")
            
            # Calculate all time stats
            all_songs = df.groupby(['master_metadata_album_artist_name', 'master_metadata_track_name']).agg(
                total_plays=('ms_played', 'count'),
                real_plays=('ms_played', lambda x: (x >= 25000).sum()),
                selections=('reason_start', lambda x: (x == 'clickrow').sum()),
                skips=('ms_played', lambda x: (x < 25000).sum()),
                first_played=('date', 'min'),
                last_played=('date', 'max')
            ).reset_index()
            
            all_songs = all_songs[all_songs['total_plays'] >= 3]
            
            # Calculate peak fixations using proper rolling windows
            progress_bar = st.progress(0)
            peak_fixations = []
            
            for idx, row in all_songs.iterrows():
                song_data = df[(df['master_metadata_album_artist_name'] == row['master_metadata_album_artist_name']) & 
                              (df['master_metadata_track_name'] == row['master_metadata_track_name'])]
                peak_fix, peak_date, window_stats = calculate_peak_fixation(song_data)
                peak_fixations.append({'peak_fixation': peak_fix, 'peak_date': peak_date})
                progress_bar.progress(min(1.0, (idx + 1) / len(all_songs)))
            
            peak_df = pd.DataFrame(peak_fixations)
            all_songs = pd.concat([all_songs, peak_df], axis=1)
            all_songs['song_id'] = all_songs['master_metadata_album_artist_name'] + " - " + all_songs['master_metadata_track_name']
            
            # Separate filtered and unfiltered
            unfiltered = all_songs[~all_songs['song_id'].isin(st.session_state.filtered_songs)]
            filtered = all_songs[all_songs['song_id'].isin(st.session_state.filtered_songs)]
            display_df = pd.concat([unfiltered, filtered]).reset_index(drop=True)
            
            # Display controls
            col1, col2 = st.columns([1, 1])
            with col2:
                songs_per_page = st.selectbox("Songs per page", [25, 50, 100, 500], index=2)
            
            # Display table with pagination
            total_songs = len(display_df)
            total_pages = (total_songs - 1) // songs_per_page + 1 if total_songs > 0 else 1
            
            if 'all_time_page' not in st.session_state:
                st.session_state.all_time_page = 0
            
            start_idx = st.session_state.all_time_page * songs_per_page
            end_idx = min(start_idx + songs_per_page, total_songs)
            
            if total_songs > 0:
                page_df = display_df.iloc[start_idx:end_idx].copy()
                
                # Create display table
                for idx, row in page_df.iterrows():
                    col1, col2 = st.columns([9, 1])
                    with col1:
                        st.write(f"**{row['master_metadata_track_name']}** by {row['master_metadata_album_artist_name']}")
                        st.caption(f"Real Plays: {row['real_plays']} | Selections: {row['selections']} | Skips: {row['skips']} | Total: {row['total_plays']} | Peak Fixation: {row['peak_fixation']:.2f} | Peak Date: {row['peak_date']} | First: {row['first_played']} | Last: {row['last_played']}")
                    with col2:
                        is_filtered = row['song_id'] in st.session_state.filtered_songs
                        if st.checkbox("Filter", value=is_filtered, key=f"all_time_{idx}"):
                            st.session_state.filtered_songs.add(row['song_id'])
                        else:
                            st.session_state.filtered_songs.discard(row['song_id'])
            
            # Pagination controls
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.button("← Previous", disabled=st.session_state.all_time_page == 0):
                    st.session_state.all_time_page -= 1
                    st.rerun()
            with col2:
                st.write(f"Page {st.session_state.all_time_page + 1} of {total_pages}")
            with col3:
                if st.button("Next →", disabled=st.session_state.all_time_page >= total_pages - 1):
                    st.session_state.all_time_page += 1
                    st.rerun()
            
            # Export button
            st.divider()
            if st.button("Export Song List", use_container_width=True):
                unfiltered_songs = display_df[~display_df['song_id'].isin(st.session_state.filtered_songs)]
                text_data = "\n".join([f"{row['master_metadata_track_name']} - {row['master_metadata_album_artist_name']}" 
                                       for _, row in unfiltered_songs.iterrows()])
                st.download_button(
                    label="Download Playlist",
                    data=text_data,
                    file_name="spotify_playlist.txt",
                    mime="text/plain"
                )
            
            st.markdown("""
            **How to Create Your Playlist in Spotify**
            1. Download your song list using the button above
            2. Go to [Spotlistr.com](https://www.spotlistr.com/)
            3. Upload your file or paste the song list
            4. Connect your Spotify account
            5. Create your playlist!
            """)
        
        with tabs[1]:
            st.subheader("Recent (30 days)")
            
            # Get recent data
            max_date = df['date'].max()
            cutoff_date = max_date - timedelta(days=30)
            recent_df = df[df['date'] >= cutoff_date]
            
            if len(recent_df) == 0:
                st.warning("No plays in the last 30 days")
            else:
                # Calculate recent stats
                recent_songs = recent_df.groupby(['master_metadata_album_artist_name', 'master_metadata_track_name']).agg(
                    total_plays=('ms_played', 'count'),
                    real_plays=('ms_played', lambda x: (x >= 25000).sum()),
                    selections=('reason_start', lambda x: (x == 'clickrow').sum()),
                    skips=('ms_played', lambda x: (x < 25000).sum()),
                    first_played=('date', 'min'),
                    last_played=('date', 'max')
                ).reset_index()
                
                # Calculate current fixation rating (for recent period)
                recent_songs['current_fixation'] = (
                    recent_songs['real_plays'].astype(float) + 
                    (recent_songs['selections'].astype(float) / recent_songs['total_plays'].astype(float).clip(lower=1))
                ).round(4)
                
                # Calculate all-time peak fixation for comparison
                progress_bar = st.progress(0)
                peak_fixations = []
                
                for idx, row in recent_songs.iterrows():
                    song_data = df[(df['master_metadata_album_artist_name'] == row['master_metadata_album_artist_name']) & 
                                  (df['master_metadata_track_name'] == row['master_metadata_track_name'])]
                    peak_fix, peak_date, window_stats = calculate_peak_fixation(song_data)
                    all_time_first = song_data['date'].min()
                    all_time_last = song_data['date'].max()
                    peak_fixations.append({
                        'all_time_peak_fixation': peak_fix, 
                        'all_time_peak_date': peak_date,
                        'all_time_first': all_time_first,
                        'all_time_last': all_time_last
                    })
                    progress_bar.progress(min(1.0, (idx + 1) / len(recent_songs)))
                
                peak_df = pd.DataFrame(peak_fixations)
                recent_songs = pd.concat([recent_songs, peak_df], axis=1)
                recent_songs['song_id'] = recent_songs['master_metadata_album_artist_name'] + " - " + recent_songs['master_metadata_track_name']
                
                recent_songs = recent_songs.sort_values('current_fixation', ascending=False)
                
                # Separate filtered and unfiltered
                unfiltered = recent_songs[~recent_songs['song_id'].isin(st.session_state.filtered_songs)]
                filtered = recent_songs[recent_songs['song_id'].isin(st.session_state.filtered_songs)]
                display_df = pd.concat([unfiltered, filtered]).reset_index(drop=True)
                
                # Display table
                for idx, row in display_df.iterrows():
                    col1, col2 = st.columns([9, 1])
                    with col1:
                        st.write(f"**{row['master_metadata_track_name']}** by {row['master_metadata_album_artist_name']}")
                        st.caption(f"Real Plays: {row['real_plays']} | Selections: {row['selections']} | Skips: {row['skips']} | Total: {row['total_plays']} | Current Fixation: {row['current_fixation']:.2f} | All-Time Peak: {row['all_time_peak_fixation']:.2f} ({row['all_time_peak_date']}) | First: {row['all_time_first']} | Last: {row['all_time_last']}")
                    with col2:
                        is_filtered = row['song_id'] in st.session_state.filtered_songs
                        if st.checkbox("Filter", value=is_filtered, key=f"recent_{idx}"):
                            st.session_state.filtered_songs.add(row['song_id'])
                        else:
                            st.session_state.filtered_songs.discard(row['song_id'])
        
        with tabs[2]:
            st.subheader("Last Year (365 days)")
            
            # Get last year data
            max_date = df['date'].max()
            cutoff_date = max_date - timedelta(days=365)
            year_df = df[df['date'] >= cutoff_date]
            
            if len(year_df) == 0:
                st.warning("No plays in the last year")
            else:
                # Calculate year stats
                year_songs = year_df.groupby(['master_metadata_album_artist_name', 'master_metadata_track_name']).agg(
                    total_plays=('ms_played', 'count'),
                    real_plays=('ms_played', lambda x: (x >= 25000).sum()),
                    selections=('reason_start', lambda x: (x == 'clickrow').sum()),
                    skips=('ms_played', lambda x: (x < 25000).sum()),
                    first_played=('date', 'min'),
                    last_played=('date', 'max')
                ).reset_index()
                
                # Calculate year fixation and all-time peak
                progress_bar = st.progress(0)
                fixation_data = []
                
                for idx, row in year_songs.iterrows():
                    song_data = df[(df['master_metadata_album_artist_name'] == row['master_metadata_album_artist_name']) & 
                                  (df['master_metadata_track_name'] == row['master_metadata_track_name'])]
                    
                    # Year fixation (max in last 365 days)
                    year_song_data = song_data[song_data['date'] >= cutoff_date]
                    year_fixation = 0
                    if len(year_song_data) > 0:
                        for end_date in year_song_data['date'].unique():
                            start_date = max(end_date - timedelta(days=30), cutoff_date)
                            fixation = calculate_fixation_for_period(song_data, start_date, end_date)
                            year_fixation = max(year_fixation, fixation)
                    
                    # All-time peak
                    peak_fix, peak_date, window_stats = calculate_peak_fixation(song_data)
                    all_time_first = song_data['date'].min()
                    all_time_last = song_data['date'].max()
                    
                    fixation_data.append({
                        'year_fixation': year_fixation,
                        'all_time_peak_fixation': peak_fix,
                        'peak_date': peak_date,
                        'all_time_first': all_time_first,
                        'all_time_last': all_time_last
                    })
                    progress_bar.progress(min(1.0, (idx + 1) / len(year_songs)))
                
                fixation_df = pd.DataFrame(fixation_data)
                year_songs = pd.concat([year_songs, fixation_df], axis=1)
                year_songs['song_id'] = year_songs['master_metadata_album_artist_name'] + " - " + year_songs['master_metadata_track_name']
                
                year_songs = year_songs.sort_values('year_fixation', ascending=False)
                
                # Separate filtered and unfiltered
                unfiltered = year_songs[~year_songs['song_id'].isin(st.session_state.filtered_songs)]
                filtered = year_songs[year_songs['song_id'].isin(st.session_state.filtered_songs)]
                display_df = pd.concat([unfiltered, filtered]).reset_index(drop=True)
                
                # Display table
                for idx, row in display_df.iterrows():
                    col1, col2 = st.columns([9, 1])
                    with col1:
                        st.write(f"**{row['master_metadata_track_name']}** by {row['master_metadata_album_artist_name']}")
                        st.caption(f"Real Plays: {row['real_plays']} | Selections: {row['selections']} | Skips: {row['skips']} | Total: {row['total_plays']} | Year Fixation: {row['year_fixation']:.2f} | All-Time Peak: {row['all_time_peak_fixation']:.2f} ({row['peak_date']}) | First: {row['all_time_first']} | Last: {row['all_time_last']}")
                    with col2:
                        is_filtered = row['song_id'] in st.session_state.filtered_songs
                        if st.checkbox("Filter", value=is_filtered, key=f"year_{idx}"):
                            st.session_state.filtered_songs.add(row['song_id'])
                        else:
                            st.session_state.filtered_songs.discard(row['song_id'])

elif st.session_state.current_page == 'Playlists':
    if st.session_state.playlists is None:
        st.warning("No playlists loaded. Please go to 'Import Data' to upload your playlist data.")
    else:
        st.header("Your Playlists")
        
        playlists = st.session_state.playlists.get('playlists', [])
        
        # Create playlist summary table
        for idx, playlist in enumerate(playlists):
            playlist_name = playlist.get('name', 'Unnamed')
            items = playlist.get('items', [])
            num_songs = len(items)
            
            # Get earliest date added
            dates = []
            for item in items:
                date_str = item.get('addedDate', '')
                if date_str:
                    try:
                        dates.append(datetime.fromisoformat(date_str.replace('Z', '+00:00')).date())
                    except:
                        pass
            
            date_started = min(dates).strftime('%Y-%m-%d') if dates else 'Unknown'
            
            col1, col2, col3, col4, col5 = st.columns([4, 1, 2, 1, 1])
            
            with col1:
                st.write(f"**{playlist_name}**")
            with col2:
                view_key = f"view_{idx}"
                if st.checkbox("View Below", key=view_key, value=st.session_state.playlist_view_states.get(view_key, False)):
                    st.session_state.playlist_view_states[view_key] = True
                else:
                    st.session_state.playlist_view_states[view_key] = False
            with col3:
                st.write(date_started)
            with col4:
                st.write(str(num_songs))
            with col5:
                filter_key = f"filter_playlist_{idx}"
                
                if st.checkbox("Filter Out", key=filter_key, value=playlist_name in st.session_state.filtered_playlists):
                    st.session_state.filtered_playlists.add(playlist_name)
                    # Add all songs from this playlist to filtered_songs
                    for item in playlist.get('items', []):
                        track = item.get('track')
                        if track:
                            artist = track.get('artistName', 'Unknown')
                            track_name = track.get('trackName', 'Unknown')
                            song_id = f"{artist} - {track_name}"
                            st.session_state.filtered_songs.add(song_id)
                else:
                    st.session_state.filtered_playlists.discard(playlist_name)
            
            # Show playlist tracks if "View Below" is checked
            if st.session_state.playlist_view_states.get(f"view_{idx}", False):
                st.write(f"**Description:** {playlist.get('description', 'No description')}")
                
                items = playlist.get('items', [])
                if len(items) > 0:
                    tracks_data = []
                    for item in items:
                        track = item.get('track')
                        if track:
                            tracks_data.append({
                                'Track': track.get('trackName', 'Unknown'),
                                'Artist': track.get('artistName', 'Unknown'),
                                'Album': track.get('albumName', 'Unknown'),
                                'Date Added': item.get('addedDate', 'Unknown')
                            })
                    
                    if tracks_data:
                        tracks_df = pd.DataFrame(tracks_data)
                        st.dataframe(tracks_df, width='stretch', hide_index=True)
                
                st.divider()

elif st.session_state.current_page == 'Data Visualization':
    st.header("Data Visualization")
    
    if st.session_state.data is not None:
        df = st.session_state.data.copy()
        df = df[df['master_metadata_track_name'].notna()].copy()
        df['date'] = pd.to_datetime(df['ts']).dt.date
        
        # Dropdown menu for song list selection
        st.subheader("Choose Song List")
        
        list_options = ["Top 100 All Time Songs", "Top 100 Fixations"]
        if st.session_state.playlists:
            playlist_names = [p.get('name', 'Unnamed') for p in st.session_state.playlists.get('playlists', [])]
            list_options.extend(playlist_names)
        
        selected_list = st.selectbox("Select a list to visualize", list_options)
        
        if selected_list == "Top 100 All Time Songs":
            # Get top songs by real plays
            song_stats = df.groupby(['master_metadata_album_artist_name', 'master_metadata_track_name']).agg(
                real_plays=('ms_played', lambda x: (x >= 25000).sum()),
                first_played=('date', 'min')
            ).reset_index()
            
            song_stats = song_stats[song_stats['real_plays'] > 0]
            song_stats['song_id'] = song_stats['master_metadata_album_artist_name'] + " - " + song_stats['master_metadata_track_name']
            unfiltered_songs = song_stats[~song_stats['song_id'].isin(st.session_state.filtered_songs)]
            top_songs = unfiltered_songs.sort_values('real_plays', ascending=False).head(100)
            
            display_songs = top_songs.sort_values('first_played')
            
        elif selected_list == "Top 100 Fixations":
            # Calculate peak fixations using proper rolling windows
            all_songs = df.groupby(['master_metadata_album_artist_name', 'master_metadata_track_name']).agg(
                first_played=('date', 'min')
            ).reset_index()
            
            progress_bar = st.progress(0)
            fixation_results = []
            
            for idx, row in all_songs.iterrows():
                song_data = df[(df['master_metadata_album_artist_name'] == row['master_metadata_album_artist_name']) & 
                              (df['master_metadata_track_name'] == row['master_metadata_track_name'])]
                peak_fix, peak_date, window_stats = calculate_peak_fixation(song_data)
                
                fixation_results.append({
                    'master_metadata_album_artist_name': row['master_metadata_album_artist_name'],
                    'master_metadata_track_name': row['master_metadata_track_name'],
                    'peak_fixation': peak_fix,
                    'first_played': row['first_played']
                })
                progress_bar.progress(min(1.0, (idx + 1) / len(all_songs)))
            
            fixation_df = pd.DataFrame(fixation_results)
            fixation_df['song_id'] = fixation_df['master_metadata_album_artist_name'] + " - " + fixation_df['master_metadata_track_name']
            unfiltered_fixations = fixation_df[~fixation_df['song_id'].isin(st.session_state.filtered_songs)]
            top_fixations = unfiltered_fixations.sort_values('peak_fixation', ascending=False).head(100)
            
            display_songs = top_fixations.sort_values('first_played')
            
        else:
            # Selected playlist
            playlists = st.session_state.playlists.get('playlists', [])
            selected_playlist = None
            for p in playlists:
                if p.get('name') == selected_list:
                    selected_playlist = p
                    break
            
            if selected_playlist:
                playlist_songs = []
                for item in selected_playlist.get('items', []):
                    track = item.get('track')
                    if track:
                        artist = track.get('artistName', 'Unknown')
                        track_name = track.get('trackName', 'Unknown')
                        date_added = item.get('addedDate', '')
                        
                        try:
                            first_played = datetime.fromisoformat(date_added.replace('Z', '+00:00')).date()
                        except:
                            first_played = datetime.now().date()
                        
                        playlist_songs.append({
                            'master_metadata_album_artist_name': artist,
                            'master_metadata_track_name': track_name,
                            'first_played': first_played
                        })
                
                display_songs = pd.DataFrame(playlist_songs).sort_values('first_played')
            else:
                display_songs = pd.DataFrame()
        
        if len(display_songs) > 0:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.subheader("Song List")
                st.write(f"Showing {len(display_songs)} songs (sorted by first play date)")
                
                for idx, row in display_songs.iterrows():
                    if st.button(f"{row['master_metadata_track_name']} - {row['master_metadata_album_artist_name']}", key=f"song_{idx}"):
                        st.session_state.selected_song = row
            
            with col2:
                st.subheader("Monthly Peak Fixation Pivot Table")
                
                if 'selected_song' in st.session_state and not display_songs.empty:
                    selected = st.session_state.selected_song
                    
                    # Get song data
                    song_data = df[(df['master_metadata_album_artist_name'] == selected['master_metadata_album_artist_name']) & 
                                  (df['master_metadata_track_name'] == selected['master_metadata_track_name'])]
                    
                    if len(song_data) > 0:
                        # Calculate monthly fixations
                        song_data['month'] = pd.to_datetime(song_data['ts']).dt.to_period('M')
                        
                        monthly_fixations = []
                        for month in song_data['month'].unique():
                            month_data = song_data[song_data['month'] == month]
                            month_start = month.start_time.date()
                            month_end = month.end_time.date()
                            
                            fixation = calculate_fixation_for_period(song_data, month_start, month_end)
                            monthly_fixations.append({
                                'Month': str(month),
                                'Peak Fixation': fixation
                            })
                        
                        monthly_df = pd.DataFrame(monthly_fixations)
                        if len(monthly_df) > 0:
                            st.dataframe(monthly_df, width='stretch', hide_index=True)
                            
                            # Detailed analysis charts
                            st.subheader(f"Detailed Analysis: {selected['master_metadata_track_name']}")
                            
                            # Line graph of plays over time
                            monthly_plays = song_data.groupby('month').size().reset_index(name='plays')
                            monthly_plays['month'] = monthly_plays['month'].astype(str)
                            
                            fig_line = px.line(monthly_plays, x='month', y='plays', title='Plays Over Time')
                            fig_line.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')
                            st.plotly_chart(fig_line, use_container_width=True)
                            
                            # Bar graph
                            fig_bar = px.bar(monthly_plays, x='month', y='plays', title='Monthly Play Count')
                            fig_bar.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')
                            st.plotly_chart(fig_bar, use_container_width=True)
                            
                            # Scatter plot
                            song_data['day'] = pd.to_datetime(song_data['ts']).dt.date
                            daily_plays = song_data.groupby('day').size().reset_index(name='plays')
                            
                            fig_scatter = px.scatter(daily_plays, x='day', y='plays', title='Daily Play Scatter Plot')
                            fig_scatter.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')
                            st.plotly_chart(fig_scatter, use_container_width=True)
                    else:
                        st.write("No data found for selected song")
                else:
                    st.write("Click on a song to see detailed analysis")
        else:
            st.write("No songs to display")
    else:
        st.warning("Please upload your Spotify data first.")

elif st.session_state.current_page == 'Import Data':
    st.header("Import Your Spotify Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Listening History")
        st.write("Upload your Spotify extended streaming history files (JSON or ZIP format)")
        uploaded_files = st.file_uploader("Upload Spotify JSON or ZIP", type=['json', 'zip'], accept_multiple_files=True, key="listening_history")
        
        if st.button("Process Files") and uploaded_files:
            with st.spinner("Processing files..."):
                st.session_state.data = process_spotify_data(uploaded_files)
                if st.session_state.data is not None:
                    st.success(f"✅ Loaded {len(st.session_state.data):,} records")
                    st.info("Navigate to 'Listening History' to view your data")
    
    with col2:
        st.subheader("Playlists")
        st.write("Upload your Spotify playlist data (JSON format)")
        playlist_file = st.file_uploader("Upload Playlist JSON", type=['json'], key="playlist_file")
        
        if st.button("Load Playlists") and playlist_file:
            with st.spinner("Loading playlists..."):
                st.session_state.playlists = process_playlist_data(playlist_file)
                if st.session_state.playlists:
                    st.success(f"✅ Loaded {len(st.session_state.playlists.get('playlists', []))} playlists")
                    st.info("Navigate to 'Playlists' to view your playlists")
    
    st.divider()
    
    st.subheader("How to Get Your Spotify Data")
    st.write("""
    1. Go to your [Spotify Account Privacy Settings](https://www.spotify.com/account/privacy/)
    2. Scroll down to "Download your data" and request your Extended Streaming History
    3. Wait for Spotify to email you (can take up to 30 days)
    4. Download the ZIP file and upload it here
    """)
    
    # Show current data status
    st.divider()
    st.subheader("Current Data Status")
    if st.session_state.data is not None:
        st.success(f"✅ Listening history loaded: {len(st.session_state.data):,} records")
    else:
        st.info("ℹ️ No listening history loaded")
    
    if st.session_state.playlists is not None:
        st.success(f"✅ Playlists loaded: {len(st.session_state.playlists.get('playlists', []))} playlists")
    else:
        st.info("ℹ️ No playlists loaded")