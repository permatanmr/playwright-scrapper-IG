import asyncio
import json
import re
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

class TikTokProfileScraper:
    def __init__(self):
        self.browser = None
        self.page = None
        self.playwright = None
        
    async def initialize(self, headless=False):
        """Initialize the browser and page"""
        self.playwright = await async_playwright().start()
        print('Launching browser...')
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        
        self.page = await self.browser.new_page()

        # Increase default timeouts to be more resilient on slow connections
        # Note: these Page methods are synchronous in the async API and should not be awaited
        self.page.set_default_navigation_timeout(60000)
        self.page.set_default_timeout(60000)

        print('Setting user agent...')
        # Set realistic user agent
        await self.page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
    async def parse_count(self, text):
        """Parse count with K, M, B suffixes"""
        if not text:
            return 0
            
        text = text.strip().upper()
        multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000}
        
        match = re.search(r'([\d.]+)([KMB]?)', text)
        if not match:
            return 0
            
        value = float(match.group(1))
        suffix = match.group(2)
        
        return int(value * multipliers.get(suffix, 1))
    
    async def scrape_profile(self, username):
        """Scrape TikTok profile data"""
        try:
            url = f'https://www.tiktok.com/@{username}'
            print(f'Scraping profile: {url}')
            
            await self.page.goto(url, wait_until='networkidle', timeout=30000)

            # Wait for profile data to load with retries and scrolling to mitigate dynamic loading
            # Use an XPath selector for robustness
            xpath_selector = "xpath=//*[@data-e2e='user-post-item']"
            found = await self._wait_for_selector_with_retries(
                xpath_selector, timeout=30000, retries=5, interval=1
            )
            if not found:
                print('Warning: could not find post items on the page after retries; continuing but results may be incomplete')
            
            # Extract profile statistics
            profile_data = await self._extract_profile_data()
            
            # Scroll to load more videos
            await self._scroll_to_load_videos(10)
            
            # Extract video data
            videos = await self._extract_video_data()
            
            # Calculate engagement metrics
            metrics = self.calculate_engagement(profile_data, videos)
            
            return {
                'profile': profile_data,
                'video_count': len(videos),
                'videos': videos,
                'engagement': metrics
            }
            
        except PlaywrightTimeout as e:
            print(f'Timeout error: {e}')
            raise
        except Exception as e:
            print(f'Error scraping profile: {e}')
            raise
    
    async def _extract_profile_data(self):
        """Extract profile statistics from the page"""
        profile_data = await self.page.evaluate('''() => {
            const getText = (selector) => {
                const element = document.querySelector(selector);
                return element ? element.textContent.trim() : '';
            };
            
            return {
                username: getText('[data-e2e="user-title"]'),
                followers_text: getText('[data-e2e="followers-count"]'),
                following_text: getText('[data-e2e="following-count"]'),
                likes_text: getText('[data-e2e="likes-count"]'),
                bio: getText('[data-e2e="user-bio"]')
            };
        }''')
        
        # Parse the counts
        return {
            'username': profile_data['username'],
            'followers': await self.parse_count(profile_data['followers_text']),
            'following': await self.parse_count(profile_data['following_text']),
            'likes': await self.parse_count(profile_data['likes_text']),
            'bio': profile_data['bio']
        }

    async def _wait_for_selector_with_retries(self, selector, timeout=30000, retries=3, interval=1):
        """Wait for a selector with retries. Scrolls the page between attempts to trigger lazy loading.

        Returns True if selector found, False otherwise.
        """
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except PlaywrightTimeout:
            # Try retries with scrolling and short sleeps
            for attempt in range(retries):
                try:
                    # Scroll down to trigger lazy loading
                    await self.page.evaluate('window.scrollBy(0, window.innerHeight)')
                    await asyncio.sleep(interval)
                    await self.page.wait_for_selector(selector, timeout=timeout)
                    return True
                except PlaywrightTimeout:
                    # Continue trying
                    continue
                except Exception:
                    continue
        except Exception:
            return False

        return False
    
    async def _scroll_to_load_videos(self, scroll_count=10):
        """Scroll the page to load more videos"""
        for i in range(scroll_count):
            await self.page.evaluate('window.scrollBy(0, window.innerHeight)')
            await asyncio.sleep(1)
    
    async def _extract_video_data(self):
        """Extract video statistics"""
        # Use XPath inside the page context to find post items (more resilient to attribute changes)
        videos = await self.page.evaluate('''(xpath) => {
            const snapshot = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
            const nodes = [];
            for (let i = 0; i < snapshot.snapshotLength; i++) {
                nodes.push(snapshot.snapshotItem(i));
            }
            return nodes.map(video => {
                const getCount = (selector) => {
                    const element = video.querySelector(selector);
                    return element ? element.textContent.trim() : '0';
                };

                return {
                    views_text: getCount('[data-e2e="video-views"]')
                };
            });
        }''', "//*[@data-e2e='user-post-item']")
        
        # Parse video counts
        parsed_videos = []
        for video in videos:
            parsed_videos.append({
                'views': await self.parse_count(video['views_text'])
            })
        
        return parsed_videos
    
    def calculate_engagement(self, profile, videos):
        """Calculate engagement metrics"""
        followers = profile['followers']
        likes = profile['likes']
        video_count = len(videos)
        
        # Total engagement rate (based on total likes)
        total_engagement_rate = (likes / followers * 100) if followers > 0 else 0
        
        # Average views per video
        total_views = sum(video['views'] for video in videos)
        avg_views = total_views / video_count if video_count > 0 else 0
        
        # View-to-follower ratio
        view_follower_ratio = (avg_views / followers * 100) if followers > 0 else 0
        
        return {
            'total_engagement_rate': f'{total_engagement_rate:.2f}%',
            'avg_views_per_video': int(avg_views),
            'view_follower_ratio': f'{view_follower_ratio:.2f}%',
            'total_likes': likes,
            'total_followers': followers,
            'total_views': total_views
        }
    
    async def close(self):
        """Close browser and cleanup"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


async def main():
    """Main function to run the scraper"""
    scraper = TikTokProfileScraper()
    
    try:
        print('Initializing scraper...')
        await scraper.initialize(headless=False)
        
        print('Scraping profile data...')
        username = '_futariii'  # Replace with target username
        data = await scraper.scrape_profile(username)
        
        # Print results
        print('\n' + '='*50)
        print('TikTok Profile Analysis')
        print('='*50)
        print(f"Username: @{data['profile']['username']}")
        print(f"Followers: {data['profile']['followers']:,}")
        print(f"Following: {data['profile']['following']:,}")
        print(f"Total Likes: {data['profile']['likes']:,}")
        print(f"Videos Analyzed: {data['video_count']}")
        
        print('\n' + '='*50)
        print('Engagement Metrics')
        print('='*50)
        print(f"Engagement Rate: {data['engagement']['total_engagement_rate']}")
        print(f"Avg Views/Video: {data['engagement']['avg_views_per_video']:,}")
        print(f"View/Follower Ratio: {data['engagement']['view_follower_ratio']}")
        print(f"Total Views: {data['engagement']['total_views']:,}")
        
        # Save to JSON
        filename = f'tiktok_{username}_profile.json'
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f'\nData saved to {filename}')
        
    except Exception as e:
        print(f'Scraping failed: {e}')
    finally:
        await scraper.close()


if __name__ == '__main__':
    asyncio.run(main())