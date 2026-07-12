"""
Example usage of JOB_RESULT_NORMALIZER agent.

This demonstrates how to use the normalize_job_result function
to parse and normalize job search results.
"""

import asyncio
from job_result_normalizer import normalize_job_result


async def example_single_job_posting():
    """Example: Normalize a single job posting"""
    
    result = await normalize_job_result(
        role_title="AI Engineer",
        target_location="San Francisco, CA",
        search_query='"AI Engineer" "San Francisco" site:builtinsf.com',
        source={
            "url": "https://www.builtinsf.com/job/ai-engineer-llm-rag-examplecorp/12345",
            "title": "AI Engineer - LLMs & RAG - ExampleCorp | Built In San Francisco",
            "snippet": "ExampleCorp is hiring an AI Engineer in San Francisco, CA to build LLM and RAG systems. Must have 3+ years experience with Python, LangChain, and vector databases. Posted 5 days ago.",
            "raw_html": None  # Optional
        }
    )
    
    print("=== Single Job Posting ===")
    print(f"Kind: {result['kind']}")
    print(f"Relevant: {result['is_relevant']}")
    print(f"Confidence: {result['confidence']}")
    
    if result.get('job_posting'):
        job = result['job_posting']
        print(f"Title: {job.get('title')}")
        print(f"Company: {job.get('company_name')}")
        print(f"Location: {job.get('location')}")
        print(f"Skills: {job.get('skills')}")
    
    return result


async def example_listing_page():
    """Example: Normalize a job listing/aggregator page"""
    
    result = await normalize_job_result(
        role_title="AI Engineer",
        target_location="San Francisco, CA",
        search_query='"AI Engineer" jobs San Francisco',
        source={
            "url": "https://www.builtinsf.com/jobs/data-analytics",
            "title": "Best Data & Analytics Jobs in San Francisco | Built In SF",
            "snippet": "Browse 25+ Data & Analytics jobs in San Francisco. AI Engineer at TechCorp, Data Scientist at StartupXYZ, Machine Learning Engineer at BigCo...",
            "raw_html": None
        }
    )
    
    print("\n=== Listing Page ===")
    print(f"Kind: {result['kind']}")
    print(f"Relevant: {result['is_relevant']}")
    
    if result.get('listing_meta'):
        meta = result['listing_meta']
        print(f"List Type: {meta.get('list_type')}")
        print(f"Estimated Jobs: {meta.get('estimated_job_count')}")
    
    if result.get('job_posting'):
        # Best matching job from the list
        job = result['job_posting']
        print(f"Best Match: {job.get('title')} at {job.get('company_name')}")
    
    return result


async def example_noise():
    """Example: Normalize irrelevant content (should be marked as noise)"""
    
    result = await normalize_job_result(
        role_title="AI Engineer",
        target_location="San Francisco, CA",
        search_query='"AI Engineer" blog',
        source={
            "url": "https://example.com/blog/how-to-become-an-ai-engineer",
            "title": "How to Become an AI Engineer: A Complete Guide",
            "snippet": "Learn everything you need to know about becoming an AI engineer. This comprehensive guide covers skills, education, and career paths...",
            "raw_html": None
        }
    )
    
    print("\n=== Noise (Irrelevant) ===")
    print(f"Kind: {result['kind']}")
    print(f"Relevant: {result['is_relevant']}")
    print(f"Reason: {result['reason']}")
    
    return result


async def main():
    """Run all examples"""
    print("Running JOB_RESULT_NORMALIZER examples...\n")
    
    # Make sure DEEPSEEK_API_KEY is set
    import os
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("⚠️  Warning: DEEPSEEK_API_KEY not set. Examples will fail.")
        return
    
    try:
        await example_single_job_posting()
        await example_listing_page()
        await example_noise()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

