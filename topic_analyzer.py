"""LangChain-based topic analyzer for YouTube video data."""

import os
from typing import List, Dict, Tuple
from collections import Counter
import pandas as pd
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain.schema import Document
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

load_dotenv()


class TopicAnalyzer:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        self.embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
        
    def extract_topics(self, videos: List[Dict]) -> List[Dict]:
        """
        Extract main topics from video titles and descriptions.
        
        Args:
            videos: List of video dictionaries
            
        Returns:
            List of videos with extracted topics
        """
        topic_extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at analyzing video content and extracting main topics.
            Extract the main topics from the video title and description.
            Focus on technical topics, frameworks, tools, and concepts.
            Return a JSON object with 'main_topic' and 'subtopics' (list of 3-5 subtopics)."""),
            ("user", "Title: {title}\n\nDescription: {description}")
        ])
        
        json_parser = JsonOutputParser()
        chain = topic_extraction_prompt | self.llm | json_parser
        
        for video in videos:
            try:
                result = chain.invoke({
                    "title": video["title"],
                    "description": video.get("description", "")[:500]  # Limit description length
                })
                
                video["main_topic"] = result.get("main_topic", "")
                video["subtopics"] = result.get("subtopics", [])
                
            except Exception as e:
                print(f"Error extracting topics for video {video['video_id']}: {e}")
                video["main_topic"] = ""
                video["subtopics"] = []
                
        return videos
    
    def cluster_similar_topics(self, videos: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Cluster videos by similar topics using embeddings.
        
        Args:
            videos: List of videos with extracted topics
            
        Returns:
            Dictionary mapping cluster topics to lists of videos
        """
        if not videos:
            return {}
            
        # Create documents from video topics
        documents = []
        for video in videos:
            if video.get("main_topic"):
                text = f"{video['main_topic']} {' '.join(video.get('subtopics', []))}"
                doc = Document(
                    page_content=text,
                    metadata={"video_id": video["video_id"], "title": video["title"]}
                )
                documents.append(doc)
        
        if not documents:
            return {}
            
        # Create vector store for similarity search
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
        splits = text_splitter.split_documents(documents)
        
        vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=self.embeddings,
            collection_name="video_topics"
        )
        
        # Use LLM to identify main topic clusters
        cluster_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at identifying trending topics and patterns.
            Based on the list of topics, identify the main topic clusters.
            Group similar topics together and provide a clear, concise name for each cluster.
            Return a JSON object with 'clusters' containing a list of cluster objects,
            each with 'name' and 'keywords' (list of related keywords)."""),
            ("user", "Topics: {topics}")
        ])
        
        all_topics = [video.get("main_topic", "") for video in videos if video.get("main_topic")]
        topic_counts = Counter(all_topics)
        
        json_parser = JsonOutputParser()
        cluster_chain = cluster_prompt | self.llm | json_parser
        
        try:
            cluster_result = cluster_chain.invoke({
                "topics": ", ".join(topic_counts.most_common(20)[i][0] for i in range(min(20, len(topic_counts))))
            })
            
            clusters = cluster_result.get("clusters", [])
            
        except Exception as e:
            print(f"Error identifying clusters: {e}")
            clusters = []
        
        # Group videos by clusters
        clustered_videos = {}
        
        for cluster in clusters:
            cluster_name = cluster["name"]
            keywords = cluster.get("keywords", [])
            clustered_videos[cluster_name] = []
            
            for video in videos:
                video_text = f"{video.get('main_topic', '')} {' '.join(video.get('subtopics', []))}"
                
                # Check if video matches any keyword in the cluster
                if any(keyword.lower() in video_text.lower() for keyword in keywords):
                    clustered_videos[cluster_name].append(video)
        
        # Add unclustered videos
        clustered_video_ids = set()
        for videos_list in clustered_videos.values():
            clustered_video_ids.update(v["video_id"] for v in videos_list)
        
        unclustered = [v for v in videos if v["video_id"] not in clustered_video_ids]
        if unclustered:
            clustered_videos["Other Topics"] = unclustered
            
        return clustered_videos
    
    def calculate_trend_scores(self, clustered_videos: Dict[str, List[Dict]]) -> List[Dict]:
        """
        Calculate trend scores for each topic cluster based on engagement metrics.
        
        Args:
            clustered_videos: Dictionary mapping topics to videos
            
        Returns:
            List of trend dictionaries sorted by score
        """
        trends = []
        
        for topic, videos in clustered_videos.items():
            if not videos:
                continue
                
            # Calculate aggregate metrics
            total_views = sum(v.get("view_count", 0) for v in videos)
            total_likes = sum(v.get("like_count", 0) for v in videos)
            total_comments = sum(v.get("comment_count", 0) for v in videos)
            video_count = len(videos)
            
            # Calculate average engagement rate
            avg_engagement_rate = 0
            if total_views > 0:
                avg_engagement_rate = (total_likes + total_comments) / total_views
            
            # Calculate trend score (weighted combination of metrics)
            # Higher weight for engagement rate and video count (indicating topic popularity)
            trend_score = (
                (total_views / 1000) * 0.2 +  # Views impact (scaled down)
                avg_engagement_rate * 10000 * 0.4 +  # Engagement rate (scaled up)
                video_count * 10 * 0.4  # Number of videos on topic
            )
            
            trends.append({
                "topic": topic,
                "trend_score": round(trend_score, 2),
                "video_count": video_count,
                "total_views": total_views,
                "total_likes": total_likes,
                "total_comments": total_comments,
                "avg_engagement_rate": round(avg_engagement_rate * 100, 2),  # As percentage
                "top_videos": sorted(videos, key=lambda x: x.get("view_count", 0), reverse=True)[:5]
            })
        
        # Sort by trend score
        trends.sort(key=lambda x: x["trend_score"], reverse=True)
        
        return trends
    
    def generate_insights(self, trends: List[Dict], area_of_interest: str) -> str:
        """
        Generate insights about the trending topics.
        
        Args:
            trends: List of trend dictionaries
            area_of_interest: The area user is interested in
            
        Returns:
            Insights text
        """
        insights_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert analyst providing insights on trending topics.
            Analyze the trend data and provide actionable insights.
            Focus on:
            1. What topics are currently most popular
            2. Why these topics might be trending
            3. Emerging topics to watch
            4. Recommendations for content creators or learners
            Keep the insights concise and actionable."""),
            ("user", "Area of Interest: {area}\n\nTop Trends:\n{trends_data}")
        ])
        
        # Prepare trends data for the prompt
        trends_summary = []
        for i, trend in enumerate(trends[:10]):  # Top 10 trends
            trends_summary.append(
                f"{i+1}. {trend['topic']}: "
                f"Score={trend['trend_score']}, "
                f"Videos={trend['video_count']}, "
                f"Engagement={trend['avg_engagement_rate']}%"
            )
        
        chain = insights_prompt | self.llm
        
        try:
            insights = chain.invoke({
                "area": area_of_interest,
                "trends_data": "\n".join(trends_summary)
            })
            return insights.content
        except Exception as e:
            print(f"Error generating insights: {e}")
            return "Unable to generate insights at this time."