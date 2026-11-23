import os

from crewai_tools import YoutubeChannelSearchTool

# Set YOUTUBE_CHANNEL_URL to the channel the agents should search,
# e.g. https://www.youtube.com/@channel-handle
yt_tool = YoutubeChannelSearchTool(youtube_channel_url=os.environ["YOUTUBE_CHANNEL_URL"])
