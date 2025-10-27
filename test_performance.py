#!/usr/bin/env python3
"""
Performance testing script for the search agent.
"""

import asyncio
import time
import statistics
from typing import List
import httpx

class PerformanceTester:
    """Test agent performance with various scenarios."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.results = []
    
    async def test_search_performance(self, query: str, user_id: str = None, iterations: int = 3):
        """Test search performance with multiple iterations."""
        print(f"\n=== Testing Query: '{query}' ===")
        times = []
        
        for i in range(iterations):
            print(f"Iteration {i+1}/{iterations}...")
            start_time = time.time()
            
            try:
                async with httpx.AsyncClient(timeout=180.0) as client:
                    payload = {"search_topic": query}
                    if user_id:
                        payload["user_id"] = user_id
                    
                    response = await client.post(f"{self.base_url}/invoke", json=payload)
                    elapsed = time.time() - start_time
                    
                    if response.status_code == 200:
                        times.append(elapsed)
                        print(f"  ✓ Success in {elapsed:.2f}s")
                    else:
                        print(f"  ✗ Failed with status {response.status_code}")
                        
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"  ✗ Error after {elapsed:.2f}s: {str(e)}")
        
        if times:
            avg_time = statistics.mean(times)
            min_time = min(times)
            max_time = max(times)
            
            print(f"Results: Avg={avg_time:.2f}s, Min={min_time:.2f}s, Max={max_time:.2f}s")
            
            self.results.append({
                "query": query,
                "user_id": user_id,
                "avg_time": avg_time,
                "min_time": min_time,
                "max_time": max_time,
                "success_rate": len(times) / iterations
            })
        
        return times
    
    async def run_performance_tests(self):
        """Run comprehensive performance tests."""
        print("Starting Performance Tests for Customer Search Agent")
        print("=" * 60)
        
        # Test scenarios
        test_cases = [
            ("How does energy shifting work?", None),
            ("What are my current energy bills?", "user12"),
            ("Solar panel information", None),
            ("Help with smart meters", "user123"),
        ]
        
        for query, user_id in test_cases:
            await self.test_search_performance(query, user_id, iterations=2)
            await asyncio.sleep(2)  # Cool down between tests
        
        self.print_summary()
    
    def print_summary(self):
        """Print performance test summary."""
        print("\n" + "=" * 60)
        print("PERFORMANCE TEST SUMMARY")
        print("=" * 60)
        
        if not self.results:
            print("No successful tests completed.")
            return
        
        total_avg = statistics.mean([r["avg_time"] for r in self.results])
        fastest = min(self.results, key=lambda x: x["min_time"])
        slowest = max(self.results, key=lambda x: x["max_time"])
        
        print(f"Overall Average Response Time: {total_avg:.2f}s")
        print(f"Fastest Query: '{fastest['query']}' in {fastest['min_time']:.2f}s")
        print(f"Slowest Query: '{slowest['query']}' in {slowest['max_time']:.2f}s")
        
        # Performance goals
        print("\nPerformance Goals:")
        fast_queries = sum(1 for r in self.results if r["avg_time"] < 15)
        print(f"  Queries under 15s: {fast_queries}/{len(self.results)} ({fast_queries/len(self.results)*100:.0f}%)")
        
        very_fast_queries = sum(1 for r in self.results if r["avg_time"] < 10)
        print(f"  Queries under 10s: {very_fast_queries}/{len(self.results)} ({very_fast_queries/len(self.results)*100:.0f}%)")
        
        print("\nRecommendations:")
        if total_avg > 30:
            print("  ⚠️  Average response time is high - check timeout configurations")
        elif total_avg > 15:
            print("  ⚠️  Response time could be improved - consider optimizations")
        else:
            print("  ✅ Response times are good!")

async def main():
    """Run performance tests."""
    tester = PerformanceTester()
    
    print("Waiting for agent to be ready...")
    await asyncio.sleep(5)
    
    try:
        await tester.run_performance_tests()
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
    except Exception as e:
        print(f"\nTest error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())