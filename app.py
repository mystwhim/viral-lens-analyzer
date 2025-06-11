import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
from datetime import datetime
import isodate
import gspread
from gspread_dataframe import set_with_dataframe

# 🌈 UIデザイン設定
st.set_page_config(page_title="ViralLens - YouTube Analyzer", layout="centered")
st.markdown("""
<style>
body {
    background: linear-gradient(160deg, #ffcccc, #ffd6e0, #e6ccff, #cceeff, #ffffff);
    background-attachment: fixed;
}
.title-container {
    text-align: center;
    margin-top: 3rem;
    margin-bottom: 2rem;
}
.title-container h1 {
    font-size: 3rem;
    font-weight: 700;
    margin-bottom: 0.3rem;
}
.title-container h3 {
    font-size: 1.2rem;
    font-weight: 400;
    color: #444;
}
.stTextInput > div > div > input {
    background-color: #ffffffdd;
    border-radius: 8px;
    padding: 10px;
}
.stButton button {
    background-color: #d9534f;
    color: white;
    font-size: 1.1rem;
    font-weight: bold;
    border-radius: 10px;
    padding: 0.6rem 1.5rem;
    margin-top: 1rem;
}
.stButton button:hover {
    background-color: #c9302c;
}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="title-container"><h1>ViralLens</h1><h3>YouTube Analyzer</h3></div>', unsafe_allow_html=True)

# 📥 入力欄
channel_id = st.text_input("Enter Channel ID or @handle")
sheet_url = st.text_input("Enter Google Spreadsheet URL")
start = st.button("Start Analysis")

# 🔐 認証とYouTube API呼び出し
def get_youtube_service():
    credentials = service_account.Credentials.from_service_account_file(
        "client_secret.json",
        scopes=[
            "https://www.googleapis.com/auth/youtube.force-ssl",
            "https://www.googleapis.com/auth/spreadsheets"
        ]
    )
    return build("youtube", "v3", credentials=credentials), credentials

# 📹 動画データ取得
def get_video_details(youtube, uploads_playlist_id):
    video_data = []
    next_page_token = None

    while len(video_data) < 1000:
        pl_request = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token
        )
        pl_response = pl_request.execute()
        video_ids = [item["contentDetails"]["videoId"] for item in pl_response["items"]]

        vid_request = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(video_ids)
        )
        vid_response = vid_request.execute()

        for item in vid_response["items"]:
            snippet = item["snippet"]
            stats = item["statistics"]
            content = item["contentDetails"]
            url = f"https://www.youtube.com/watch?v={item['id']}"
            published_at = snippet["publishedAt"]
            duration = isodate.parse_duration(content["duration"]).total_seconds()
            is_shorts = "shorts" in url or duration < 60

            video_data.append({
                "Title": snippet["title"],
                "Description": snippet.get("description", ""),
                "Published At": published_at,
                "Views": stats.get("viewCount", "0"),
                "Likes": stats.get("likeCount", "0"),
                "Comments": stats.get("commentCount", "0"),
                "Duration": content["duration"],
                "Shorts": is_shorts,
                "URL": url,
                "Video ID": item["id"],
                "Thumbnail": snippet["thumbnails"]["high"]["url"]
            })

        next_page_token = pl_response.get("nextPageToken")
        if not next_page_token:
            break

    return video_data[:1000]

# 📤 Googleスプレッドシートへ出力
def write_to_sheet(credentials, sheet_url, df):
    gc = gspread.authorize(credentials)
    spreadsheet = gc.open_by_url(sheet_url)
    worksheet = spreadsheet.sheet1
    worksheet.clear()
    set_with_dataframe(worksheet, df)

# 🚀 実行処理
if start:
    try:
        youtube, credentials = get_youtube_service()
        if "@" in channel_id:
            req = youtube.channels().list(part="contentDetails", forUsername=channel_id.replace("@", ""))
        else:
            req = youtube.channels().list(part="contentDetails", id=channel_id)
        res = req.execute()

        uploads_id = res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        data = get_video_details(youtube, uploads_id)
        df = pd.DataFrame(data)

        write_to_sheet(credentials, sheet_url, df)

        st.success("Analysis Complete!")
        st.dataframe(df)

    except Exception as e:
        st.error(f"Error: {e}")
