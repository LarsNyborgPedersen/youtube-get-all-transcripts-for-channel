import os
import re
import requests
from tqdm import tqdm
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

def get_channel_id_from_handle(handle_url):
    html = requests.get(handle_url).text
    match = re.search(r'"channelId":"(UC[\w-]+)"', html)
    if match:
        return match.group(1)
    raise ValueError("Could not extract channel ID from handle URL")

def get_video_urls_from_channel(channel_url, max_total=5000):
    if "/@" in channel_url or "@@" in channel_url:
        channel_id = get_channel_id_from_handle(channel_url)
    elif "/channel/" in channel_url:
        channel_id = channel_url.split("/channel/")[-1]
    else:
        raise ValueError("Unsupported channel URL format")

    video_urls = []
    next_page_token = None
    base_url = "https://www.googleapis.com/youtube/v3/search"

    while True:
        params = {
            "key": YOUTUBE_API_KEY,
            "channelId": channel_id,
            "part": "snippet",
            "order": "date",
            "maxResults": 50,
            "type": "video",
        }

        if next_page_token:
            params["pageToken"] = next_page_token

        res = requests.get(base_url, params=params)
        data = res.json()

        if "items" not in data:
            raise Exception(f"Error from YouTube API: {data}")

        video_ids = [item["id"]["videoId"] for item in data["items"]]
        video_urls += [f"https://www.youtube.com/watch?v={vid}" for vid in video_ids]

        next_page_token = data.get("nextPageToken")
        if not next_page_token or len(video_urls) >= max_total:
            break

    return video_urls


def seconds_to_hhmmss(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def generate_transcripts(channel_url, output_dir="transcripts"):
    os.makedirs(output_dir, exist_ok=True)
    video_urls = get_video_urls_from_channel(channel_url)
    for idx, video_url in enumerate(tqdm(video_urls, desc="Processing videos"), start=1):
        video_id = video_url.split("v=")[-1]
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
        except:
            continue  # skip videos without captions
        try:
            video_title = YouTube(video_url).title
        except:
            video_title = f"Video_{idx}"  # fallback

        sanitized_title = sanitize_filename(video_title)
        output_file = os.path.join(output_dir, f"{idx:03d}_{sanitized_title}.md")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# 📹 {video_title}\n")
            f.write(f"🔗 {video_url}\n\n")

            for entry in transcript:
                ts = seconds_to_hhmmss(entry['start'])
                text = entry['text'].replace('\n', ' ')
                f.write(f"- {ts} {text}\n")
            f.write("\n---\n\n")

    print(f"\n✅ Done! Transcripts saved to `{output_dir}` directory")

if __name__ == "__main__":
    channel_url = input("Enter YouTube channel URL or ID: ").strip()
    if not channel_url.startswith("http"):
        channel_url = f"https://www.youtube.com/channel/{channel_url}"
    generate_transcripts(channel_url)
