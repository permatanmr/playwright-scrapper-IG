import asyncio
import json
import re
from datetime import datetime
from playwright.async_api import async_playwright

class AdvancedTikTokXPathScraper:
    """Advanced TikTok scraper using XPath selectors"""
    
    # XPath constants
    XPATHS = {
        'username': '//h1[@data-e2e="user-title"]',
        'subtitle': '//h2[@data-e2e="user-subtitle"]',
        'bio': '//h2[@data-e2e="user-bio"]',
        'followers_count': '//strong[@data-e2e="followers-count"]',
        'following_count': '//strong[@data-e2e="following-count"]',
        'likes_count': '//strong[@data-e2e="likes-count"]',
        'verified_badge': '//div[@data-e2e="user-verified-badge"]',
        'video_items': '//div[@data-e2e="user-post-item"]',
        'video_views': './/strong[@data-e2e="video-views"]',
        'video_link': './/a[contains(@href, "/video/")]',
        # Alternative XPaths for different layouts
        'followers_alt': '//div[contains(@class, "tiktok-")]//strong[1]',
        'following_alt': '//div[contains(@class, "tiktok-")]//strong[2]',
        'likes_alt': '//div[contains(@class, "tiktok-")]//strong[3]',
    }
    
    def __init__(self, headless=False, timeout=30000):
        self.browser = None
        self.page = None
        self.playwright = None
        self.headless = headless
        self.timeout = timeout
        
    async def __aenter__(self):
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    async def initialize(self):
        """Initialize browser with XPath support"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        self.page = await context.new_page()
        
    async def get_element_text(self, xpath, default=''):
        """Get text from element using XPath"""
        try:
            element = await self.page.query_selector(f'xpath={xpath}')
            if element:
                return (await element.inner_text()).strip()
        except Exception as e:
            print(f'Error getting text for xpath {xpath}: {e}')
        return default
    
    async def get_elements(self, xpath):
        """Get all elements matching XPath"""
        try:
            return await self.page.query_selector_all(f'xpath={xpath}')
        except Exception as e:
            print(f'Error getting elements for xpath {xpath}: {e}')
            return []
    
    async def element_exists(self, xpath):
        """Check if element exists using XPath"""
        try:
            element = await self.page.query_selector(f'xpath={xpath}')
            return element is not None
        except:
            return False
    
    async def parse_count(self, text):
        """Parse numerical values with K/M/B suffixes"""
        if not text:
            return 0
        
        text = str(text).strip().upper().replace(',', '')
        multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000}
        
        match = re.search(r'([\d.]+)([KMB]?)', text)
        if not match:
            return 0
        
        value = float(match.group(1))
        suffix = match.group(2)
        
        return int(value * multipliers.get(suffix, 1))
    
    async def scrape_profile(self, username, max_videos=30):
        """Scrape comprehensive profile data using XPath"""
        url = f'https://www.tiktok.com/@{username}'
        print(f'📱 Scraping: {url}')
        
        try:
            await self.page.goto(url, wait_until='domcontentloaded', timeout=self.timeout)
            await asyncio.sleep(3)
            
            # Wait for video items or profile data
            try:
                await self.page.wait_for_selector(f'xpath={self.XPATHS["video_items"]}', timeout=10000)
            except:
                print('⚠️ Warning: Could not find videos, checking if profile exists...')
            
            # Extract profile data
            profile = await self._extract_profile_stats()
            
            # Load videos
            videos = await self._load_videos(max_videos)
            
            # Calculate metrics
            metrics = self._calculate_metrics(profile, videos)
            
            return {
                'scraped_at': datetime.now().isoformat(),
                'username': username,
                'url': url,
                'profile': profile,
                'videos': videos,
                'metrics': metrics
            }
            
        except Exception as e:
            print(f'❌ Error: {e}')
            raise
    
    async def _extract_profile_stats(self):
        """Extract profile statistics using XPath"""
        print('📊 Extracting profile stats...')
        
        # Get username
        username = await self.get_element_text(self.XPATHS['username'])
        
        # Get subtitle (unique ID)
        subtitle = await self.get_element_text(self.XPATHS['subtitle'])
        
        # Get bio
        bio = await self.get_element_text(self.XPATHS['bio'])
        
        # Get follower count
        followers_text = await self.get_element_text(self.XPATHS['followers_count'])
        if not followers_text:
            followers_text = await self.get_element_text(self.XPATHS['followers_alt'])
        followers = await self.parse_count(followers_text)
        
        # Get following count
        following_text = await self.get_element_text(self.XPATHS['following_count'])
        if not following_text:
            following_text = await self.get_element_text(self.XPATHS['following_alt'])
        following = await self.parse_count(following_text)
        
        # Get total likes
        likes_text = await self.get_element_text(self.XPATHS['likes_count'])
        if not likes_text:
            likes_text = await self.get_element_text(self.XPATHS['likes_alt'])
        total_likes = await self.parse_count(likes_text)
        
        # Check verified status
        verified = await self.element_exists(self.XPATHS['verified_badge'])
        
        profile_data = {
            'username': username,
            'subtitle': subtitle,
            'bio': bio,
            'followers': followers,
            'following': following,
            'total_likes': total_likes,
            'verified': verified
        }
        
        print(f'✅ Profile stats extracted: {followers:,} followers, {total_likes:,} likes')
        return profile_data
    
    async def _load_videos(self, max_videos=30):
        """Load and extract video data using XPath"""
        print(f'🎥 Loading up to {max_videos} videos...')
        
        videos = []
        scroll_attempts = 0
        max_scrolls = 20
        last_count = 0
        no_change_count = 0
        
        while len(videos) < max_videos and scroll_attempts < max_scrolls:
            # Get current video elements
            video_elements = await self.get_elements(self.XPATHS['video_items'])
            current_count = len(video_elements)
            
            # Extract video data
            for idx, video_element in enumerate(video_elements[:max_videos]):
                if idx >= len(videos):
                    try:
                        # Get views using relative XPath
                        views_text = await self.get_element_text(self.XPATHS['video_views'])
                        if not views_text:
                            # Try to get from child element
                            views_element = await video_element.query_selector(f'xpath={self.XPATHS["video_views"]}')
                            views_text = await views_element.inner_text() if views_element else '0'
                        
                        # Try to get video URL
                        link_element = await video_element.query_selector(f'xpath={self.XPATHS["video_link"]}')
                        video_url = await link_element.get_attribute('href') if link_element else ''
                        
                        videos.append({
                            'index': idx + 1,
                            'views': await self.parse_count(views_text),
                            'url': video_url if video_url else None
                        })
                        
                    except Exception as e:
                        print(f'⚠️ Error extracting video {idx + 1}: {e}')
                        videos.append({
                            'index': idx + 1,
                            'views': 0,
                            'url': None
                        })
            
            # Check if we got new videos
            if current_count == last_count:
                no_change_count += 1
                if no_change_count >= 3:
                    print('🛑 No new videos loaded after 3 attempts')
                    break
            else:
                no_change_count = 0
            
            last_count = current_count
            
            # Scroll
            await self.page.evaluate('window.scrollBy(0, window.innerHeight)')
            await asyncio.sleep(1.5)
            scroll_attempts += 1
            
            print(f'📜 Scroll {scroll_attempts}/{max_scrolls}: {len(videos)} videos loaded')
            
            if len(videos) >= max_videos:
                break
        
        print(f'✅ Loaded {len(videos)} videos')
        return videos[:max_videos]
    
    def _calculate_metrics(self, profile, videos):
        """Calculate engagement and performance metrics"""
        followers = profile['followers']
        total_likes = profile['total_likes']
        video_count = len(videos)
        
        if video_count == 0:
            return {
                'error': 'No videos found to analyze',
                'videos_analyzed': 0
            }
        
        total_views = sum(v['views'] for v in videos)
        avg_views = total_views / video_count
        max_views = max((v['views'] for v in videos), default=0)
        min_views = min((v['views'] for v in videos), default=0)
        
        # Engagement rate (likes per follower)
        engagement_rate = (total_likes / followers * 100) if followers > 0 else 0
        
        # Views per follower
        views_per_follower = (avg_views / followers) if followers > 0 else 0
        
        # Virality score (avg views / followers * 100)
        virality_score = views_per_follower * 100
        
        # Consistency score (how consistent are view counts)
        if video_count > 1:
            import statistics
            view_counts = [v['views'] for v in videos]
            std_dev = statistics.stdev(view_counts)
            consistency = 100 - min((std_dev / avg_views * 100), 100) if avg_views > 0 else 0
        else:
            consistency = 0
        
        return {
            'total_engagement_rate': round(engagement_rate, 2),
            'avg_views_per_video': int(avg_views),
            'max_views': max_views,
            'min_views': min_views,
            'total_views_analyzed': total_views,
            'videos_analyzed': video_count,
            'views_per_follower': round(views_per_follower, 2),
            'virality_score': round(virality_score, 2),
            'consistency_score': round(consistency, 2),
            'likes_per_video_estimate': int(total_likes / video_count) if video_count > 0 else 0
        }
    
    async def close(self):
        """Cleanup resources"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


async def scrape_single_profile(username='charlidamelio'):
    """Scrape a single profile"""
    async with AdvancedTikTokXPathScraper(headless=False) as scraper:
        data = await scraper.scrape_profile(username, max_videos=20)
        
        # Print formatted results
        print('\n' + '='*70)
        print('📊 TIKTOK PROFILE ANALYSIS')
        print('='*70)
        
        profile = data['profile']
        print(f"\n👤 Profile Information:")
        print(f"   Username: @{profile['username']}")
        if profile['subtitle']:
            print(f"   ID: {profile['subtitle']}")
        if profile['bio']:
            print(f"   Bio: {profile['bio'][:100]}...")
        print(f"   Verified: {'✓ Yes' if profile['verified'] else '✗ No'}")
        print(f"   Followers: {profile['followers']:,}")
        print(f"   Following: {profile['following']:,}")
        print(f"   Total Likes: {profile['total_likes']:,}")
        
        metrics = data['metrics']
        if 'error' not in metrics:
            print(f"\n📈 Engagement Metrics:")
            print(f"   Videos Analyzed: {metrics['videos_analyzed']}")
            print(f"   Engagement Rate: {metrics['total_engagement_rate']}%")
            print(f"   Avg Views/Video: {metrics['avg_views_per_video']:,}")
            print(f"   Max Views: {metrics['max_views']:,}")
            print(f"   Min Views: {metrics['min_views']:,}")
            print(f"   Virality Score: {metrics['virality_score']}")
            print(f"   Consistency: {metrics['consistency_score']}%")
            
            # Top videos
            print(f"\n🏆 Top 5 Videos by Views:")
            sorted_videos = sorted(data['videos'], key=lambda x: x['views'], reverse=True)
            for i, video in enumerate(sorted_videos[:5], 1):
                print(f"   {i}. Video #{video['index']}: {video['views']:,} views")
        
        # Save to JSON
        filename = f'tiktok_{username}_xpath_analysis.json'
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f'\n💾 Data saved to {filename}')
        print('='*70)
        
        return data


async def compare_multiple_profiles(usernames):
    """Compare multiple profiles"""
    results = []
    
    async with AdvancedTikTokXPathScraper(headless=False) as scraper:
        for username in usernames:
            try:
                print(f'\n{"="*70}')
                data = await scraper.scrape_profile(username, max_videos=15)
                results.append(data)
                
                profile = data['profile']
                metrics = data['metrics']
                
                print(f"✅ @{username}")
                print(f"   Followers: {profile['followers']:,}")
                print(f"   Engagement: {metrics.get('total_engagement_rate', 'N/A')}%")
                print(f"   Avg Views: {metrics.get('avg_views_per_video', 'N/A'):,}")
                
                await asyncio.sleep(5)  # Delay between profiles
                
            except Exception as e:
                print(f"❌ Failed @{username}: {e}")
    
    # Save comparison
    filename = 'tiktok_comparison.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f'\n💾 Comparison saved to {filename}')
    return results


# Example usage
if __name__ == '__main__':
    # Single profile analysis
    asyncio.run(scrape_single_profile('_futariii'))
    
    # Multiple profiles comparison
    # asyncio.run(compare_multiple_profiles(['charlidamelio', 'khaby.lame', 'bellapoarch']))