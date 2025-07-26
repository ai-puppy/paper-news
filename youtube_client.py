"""YouTube API client for fetching video data."""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
from api_utils import handle_api_errors, rate_limit, QuotaTracker

load_dotenv()


class YouTubeClient:
    def __init__(self):
        self.api_key = os.getenv("YOUTUBE_API_KEY")
        if not self.api_key:
            raise ValueError("YOUTUBE_API_KEY not found in environment variables")
        
        self.youtube = build("youtube", "v3", developerKey=self.api_key)
        self.quota_tracker = QuotaTracker()
    
    @handle_api_errors
    @rate_limit(calls_per_second=10)
    def search_videos(
        self, 
        query: str, 
        max_results: int = 50,
        days_back: int = 7,
        order: str = "relevance"
    ) -> List[Dict]:
        """
        Search for videos based on query and time range.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            days_back: Number of days to look back
            order: Sort order (relevance, date, rating, viewCount)
        
        Returns:
            List of video dictionaries with metadata
        """
        # Use UTC time for consistency with YouTube API
        published_after = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"
        
        videos = []
        next_page_token = None
        
        while len(videos) < max_results:
            # Track quota usage
            self.quota_tracker.track_operation("search.list")
            
            request = self.youtube.search().list(
                q=query,
                part="snippet",
                type="video",
                maxResults=min(50, max_results - len(videos)),
                order=order,
                publishedAfter=published_after,
                pageToken=next_page_token
            )
            
            response = request.execute()
            
            for item in response.get("items", []):
                videos.append({
                    "video_id": item["id"]["videoId"],
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "channel_title": item["snippet"]["channelTitle"],
                    "published_at": item["snippet"]["publishedAt"],
                    "thumbnail_url": item["snippet"]["thumbnails"].get("high", {}).get("url", "")
                })
            
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
                
        return videos[:max_results]
    
    @handle_api_errors
    @rate_limit(calls_per_second=10)
    def get_video_statistics(self, video_ids: List[str]) -> Dict[str, Dict]:
        """
        Get statistics for a list of video IDs.
        
        Args:
            video_ids: List of YouTube video IDs
            
        Returns:
            Dictionary mapping video_id to statistics
        """
        stats = {}
        
        # YouTube API allows max 50 IDs per request
        for i in range(0, len(video_ids), 50):
            batch_ids = video_ids[i:i+50]
            
            # Track quota usage
            self.quota_tracker.track_operation("videos.list")
            
            request = self.youtube.videos().list(
                part="statistics,contentDetails",
                id=",".join(batch_ids)
            )
            
            response = request.execute()
            
            for item in response.get("items", []):
                video_id = item["id"]
                stats[video_id] = {
                    "view_count": int(item["statistics"].get("viewCount", 0)),
                    "like_count": int(item["statistics"].get("likeCount", 0)),
                    "comment_count": int(item["statistics"].get("commentCount", 0)),
                    "duration": item.get("contentDetails", {}).get("duration", "PT0S")
                }
            
        return stats
    
    @handle_api_errors
    @rate_limit(calls_per_second=10)
    def get_trending_videos(self, category_id: Optional[str] = None, max_results: int = 50) -> List[Dict]:
        """
        Get trending videos.
        
        Args:
            category_id: YouTube category ID (optional)
            max_results: Maximum number of results
            
        Returns:
            List of trending video dictionaries
        """
        videos = []
        
        # Track quota usage
        self.quota_tracker.track_operation("videos.list")
        
        request = self.youtube.videos().list(
            part="snippet,statistics",
            chart="mostPopular",
            regionCode="US",
            categoryId=category_id,
            maxResults=max_results
        )
        
        response = request.execute()
        
        for item in response.get("items", []):
            videos.append({
                "video_id": item["id"],
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"],
                "channel_title": item["snippet"]["channelTitle"],
                "published_at": item["snippet"]["publishedAt"],
                "view_count": int(item["statistics"].get("viewCount", 0)),
                "like_count": int(item["statistics"].get("likeCount", 0)),
                "comment_count": int(item["statistics"].get("commentCount", 0))
            })
        
        return videos
    
    def get_quota_status(self) -> Dict[str, int]:
        """Get current quota usage status."""
        return {
            "used": self.quota_tracker.used_quota,
            "remaining": self.quota_tracker.get_remaining_quota(),
            "limit": self.quota_tracker.daily_limit
        }