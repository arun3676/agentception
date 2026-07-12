/**
 * Job Card Normalization
 * 
 * Converts raw backend job posting data into a consistent, professional format
 * for display in the UI, similar to LinkedIn/Wellfound.
 */

/**
 * Match information for job relevance scoring
 */
export type MatchInfo = {
  score: number; // 0–100
  label: "Strong match" | "Good match" | "Possible match" | "Low match";
};

// ATS domains (direct company job postings)
const ATS_DOMAINS = [
  "lever.co",
  "greenhouse.io",
  "boards.greenhouse.io",
  "ashbyhq.com",
  "jobs.ashbyhq.com",
  "workable.com",
  "smartrecruiters.com",
  "bamboohr.com",
  "myworkdayjobs.com",
];

// Job aggregator/board domains
const JOB_SOURCE_DOMAINS = [
  "hiringcafe.com",
  "jooble.org",
  "adzuna.com",
  "dice.com",
  "clearancejobs.com",
];

/**
 * Role-specific keywords for matching
 */
const ROLE_KEYWORDS: Record<string, string[]> = {
  "ai engineer": [
    "ai", "artificial intelligence", "ml", "machine learning", "llm", "large language model",
    "rag", "retrieval augmented generation", "agent", "agents", "agentic", "pytorch", "langchain",
    "inference", "mlops", "ml ops", "vector", "embeddings", "transformer", "neural network",
    "deep learning", "nlp", "natural language processing", "computer vision", "cv", "tensorflow",
    "hugging face", "openai", "anthropic", "claude", "gpt", "fine-tuning", "fine tuning",
    "prompt engineering", "chain of thought", "reinforcement learning", "rlhf",
    "reinforcement learning from human feedback"
  ],
  "backend engineer": [
    "backend", "server", "api", "rest", "graphql", "microservices", "distributed systems",
    "database", "sql", "nosql", "postgresql", "mongodb", "redis", "docker", "kubernetes",
    "aws", "azure", "gcp", "cloud", "node.js", "java", "spring", "python", "django", "flask",
    "go", "golang", "rust", "scala", "kafka", "rabbitmq", "message queue", "ci/cd", "jenkins",
    "git", "linux", "system design", "scalability", "performance"
  ],
  "data engineer": [
    "data engineer", "etl", "elt", "data pipeline", "data warehouse", "data lake",
    "spark", "hadoop", "kafka", "airflow", "prefect", "dbt", "snowflake", "redshift",
    "bigquery", "databricks", "delta lake", "parquet", "avro", "pyspark", "scala",
    "sql", "python", "pandas", "numpy", "data modeling", "data architecture",
    "streaming", "batch processing", "data quality", "data governance"
  ],
  "data analyst": [
    "data analyst", "analytics", "business intelligence", "bi", "sql", "excel", "tableau",
    "power bi", "looker", "data visualization", "dashboard", "reporting", "etl",
    "statistics", "statistical analysis", "python", "r", "pandas", "numpy", "matplotlib",
    "seaborn", "data modeling", "sql query", "data warehouse", "redshift", "bigquery",
    "snowflake", "segmentation", "kpi", "metrics", "insights", "data mining"
  ],
  "devops engineer": [
    "devops", "ci/cd", "continuous integration", "continuous deployment", "jenkins", "gitlab ci",
    "github actions", "circleci", "travis ci", "docker", "kubernetes", "k8s", "terraform",
    "ansible", "puppet", "chef", "aws", "azure", "gcp", "cloud", "infrastructure as code",
    "iac", "monitoring", "prometheus", "grafana", "elk stack", "splunk", "linux", "bash",
    "python", "groovy", "yaml", "kubernetes orchestration", "containerization", "microservices"
  ],
  "cloud engineer": [
    "cloud", "aws", "amazon web services", "azure", "microsoft azure", "gcp", "google cloud",
    "cloud infrastructure", "cloud architecture", "ec2", "s3", "lambda", "rds", "vpc",
    "cloudformation", "terraform", "kubernetes", "docker", "serverless", "cloud security",
    "cloud migration", "multi-cloud", "hybrid cloud", "iaas", "paas", "saas", "ci/cd",
    "devops", "cloud networking", "load balancing", "auto scaling", "cloud monitoring"
  ],
  "cybersecurity engineer": [
    "cybersecurity", "security", "information security", "network security", "cloud security",
    "penetration testing", "vulnerability assessment", "siem", "splunk", "security operations",
    "incident response", "threat intelligence", "firewall", "ids", "ips", "vpn", "encryption",
    "ssl", "tls", "authentication", "authorization", "iam", "identity management", "zero trust",
    "security compliance", "soc", "security operations center", "malware analysis", "forensics"
  ],
  "product manager": [
    "product manager", "product management", "product strategy", "product roadmap", "roadmap",
    "agile", "scrum", "kanban", "user stories", "requirements", "specifications", "wireframes",
    "prototyping", "figma", "user research", "ux research", "market research", "competitive analysis",
    "analytics", "metrics", "kpi", "okr", "go-to-market", "gtm", "product launch", "a/b testing",
    "stakeholder management", "cross-functional", "jira", "confluence", "product owner"
  ],
  "software architect": [
    "software architect", "architecture", "system architecture", "software design", "design patterns",
    "microservices", "distributed systems", "scalability", "performance", "system design",
    "api design", "rest", "graphql", "database design", "data modeling", "cloud architecture",
    "aws", "azure", "gcp", "kubernetes", "docker", "infrastructure", "tech stack", "technology stack",
    "enterprise architecture", "solution architect", "technical leadership", "code review", "mentoring"
  ],
  "frontend engineer": [
    "frontend", "front-end", "react", "vue", "angular", "javascript", "typescript", "html", "css",
    "sass", "scss", "less", "webpack", "vite", "next.js", "nuxt", "gatsby", "remix", "svelte",
    "ui", "ux", "user interface", "responsive design", "mobile-first", "css-in-js", "styled-components",
    "tailwind", "bootstrap", "material-ui", "component library", "redux", "zustand", "context api",
    "graphql", "rest api", "fetch", "axios", "jest", "react testing library", "cypress", "storybook"
  ],
  "full-stack developer": [
    "full stack", "full-stack", "react", "vue", "angular", "javascript", "typescript",
    "node.js", "express", "next.js", "html", "css", "sass", "webpack", "vite",
    "backend", "frontend", "api", "rest", "graphql", "database", "mongodb", "postgresql",
    "aws", "vercel", "deployment", "ci/cd", "testing", "jest", "cypress"
  ],
  "java developer": [
    "java", "spring", "spring boot", "spring framework", "hibernate", "jpa", "maven", "gradle",
    "microservices", "rest api", "soap", "junit", "mockito", "multithreading", "concurrency",
    "jvm", "java ee", "jakarta ee", "servlet", "jsp", "spring mvc", "spring cloud", "kafka",
    "rabbitmq", "elasticsearch", "apache", "tomcat", "jetty", "intellij", "eclipse", "design patterns",
    "object-oriented", "oop", "sql", "oracle", "mysql", "postgresql", "nosql", "mongodb"
  ],
  "machine learning engineer": [
    "machine learning", "ml", "deep learning", "neural network", "pytorch", "tensorflow",
    "scikit-learn", "xgboost", "feature engineering", "model training", "model deployment",
    "mlops", "ml ops", "kubernetes", "docker", "python", "pandas", "numpy", "jupyter",
    "experiment tracking", "model monitoring", "a/b testing", "computer vision", "nlp"
  ],
  "mobile developer": [
    "mobile developer", "ios", "android", "react native", "flutter", "swift", "kotlin", "java",
    "objective-c", "xcode", "android studio", "app development", "mobile app", "sdk", "api integration",
    "firebase", "push notifications", "app store", "play store", "ui/ux", "responsive design",
    "cross-platform", "native", "hybrid", "xamarin", "cordova", "ionic", "mobile architecture",
    "mvvm", "mvc", "redux", "mobx", "async", "concurrency", "mobile testing", "unit testing"
  ],
  "blockchain developer": [
    "blockchain", "ethereum", "solidity", "smart contracts", "web3", "defi", "nft", "cryptocurrency",
    "bitcoin", "hyperledger", "consensus", "proof of stake", "pos", "proof of work", "pow",
    "distributed ledger", "cryptography", "hash", "merkle tree", "truffle", "hardhat", "remix",
    "ipfs", "oracle", "chainlink", "token", "erc20", "erc721", "erc1155", "metamask", "wallet",
    "dapp", "decentralized application", "rust", "go", "javascript", "typescript", "node.js"
  ],
};

/**
 * Get keywords for a given role (case-insensitive lookup with fuzzy matching)
 */
function getKeywordsForRole(role: string | null | undefined): string[] {
  if (!role) return [];
  
  const roleLower = role.toLowerCase().trim();
  
  // Try exact match first
  if (ROLE_KEYWORDS[roleLower]) {
    return ROLE_KEYWORDS[roleLower];
  }
  
  // Try partial match - check if role contains key or key contains role
  for (const [key, keywords] of Object.entries(ROLE_KEYWORDS)) {
    // Check if role contains the key (e.g., "Backend Engineer" contains "backend engineer")
    if (roleLower.includes(key)) {
      return keywords;
    }
    // Check if key contains the role (e.g., "backend engineer" contains "backend")
    if (key.includes(roleLower) && roleLower.length >= 3) {
      return keywords;
    }
  }
  
  // Try keyword-based matching for common patterns (ordered by specificity)
  // Check more specific patterns first
  if (roleLower.includes("data analyst")) {
    return ROLE_KEYWORDS["data analyst"] || [];
  }
  if (roleLower.includes("data engineer")) {
    return ROLE_KEYWORDS["data engineer"] || [];
  }
  if (roleLower.includes("machine learning")) {
    return ROLE_KEYWORDS["machine learning engineer"] || [];
  }
  if (roleLower.includes("artificial intelligence")) {
    return ROLE_KEYWORDS["ai engineer"] || [];
  }
  if (roleLower.includes("full stack") || roleLower.includes("full-stack") || roleLower.includes("fullstack")) {
    return ROLE_KEYWORDS["full-stack developer"] || [];
  }
  if (roleLower.includes("frontend") || roleLower.includes("front-end")) {
    return ROLE_KEYWORDS["frontend engineer"] || [];
  }
  if (roleLower.includes("devops") || roleLower.includes("dev ops")) {
    return ROLE_KEYWORDS["devops engineer"] || [];
  }
  if (roleLower.includes("cybersecurity") || roleLower.includes("cyber security")) {
    return ROLE_KEYWORDS["cybersecurity engineer"] || [];
  }
  if (roleLower.includes("software architect") || roleLower.includes("software arch")) {
    return ROLE_KEYWORDS["software architect"] || [];
  }
  if (roleLower.includes("mobile developer") || roleLower.includes("mobile dev")) {
    return ROLE_KEYWORDS["mobile developer"] || [];
  }
  if (roleLower.includes("blockchain developer") || roleLower.includes("blockchain dev")) {
    return ROLE_KEYWORDS["blockchain developer"] || [];
  }
  
  // Check single keyword patterns
  if (roleLower.includes("backend") || roleLower.includes("server")) {
    return ROLE_KEYWORDS["backend engineer"] || [];
  }
  if (roleLower.includes("data") && roleLower.includes("analyst")) {
    return ROLE_KEYWORDS["data analyst"] || [];
  }
  if (roleLower.includes("data")) {
    return ROLE_KEYWORDS["data engineer"] || [];
  }
  if (roleLower.includes("ml") || roleLower.includes("machine learning")) {
    return ROLE_KEYWORDS["machine learning engineer"] || [];
  }
  if (roleLower.includes("ai") || roleLower.includes("artificial intelligence")) {
    return ROLE_KEYWORDS["ai engineer"] || [];
  }
  if (roleLower.includes("frontend") || roleLower.includes("front-end")) {
    return ROLE_KEYWORDS["frontend engineer"] || [];
  }
  if (roleLower.includes("cloud")) {
    return ROLE_KEYWORDS["cloud engineer"] || [];
  }
  if (roleLower.includes("security")) {
    return ROLE_KEYWORDS["cybersecurity engineer"] || [];
  }
  if (roleLower.includes("product") || roleLower === "pm") {
    return ROLE_KEYWORDS["product manager"] || [];
  }
  if (roleLower.includes("architect")) {
    return ROLE_KEYWORDS["software architect"] || [];
  }
  if (roleLower.includes("java")) {
    return ROLE_KEYWORDS["java developer"] || [];
  }
  if (roleLower.includes("mobile") || roleLower.includes("ios") || roleLower.includes("android")) {
    return ROLE_KEYWORDS["mobile developer"] || [];
  }
  if (roleLower.includes("blockchain") || roleLower.includes("web3") || roleLower.includes("solidity")) {
    return ROLE_KEYWORDS["blockchain developer"] || [];
  }
  
  // Default: return empty array (no role-specific matching)
  return [];
}

/**
 * Compute match information based on keyword overlap with requested role
 * 
 * @param jobText - Concatenated text from job title, company, and snippet
 * @param requestedRole - The role the user is searching for (e.g., "Backend Engineer")
 * @returns MatchInfo with score (0-100) and label
 */
export function computeMatchInfo(jobText: string, requestedRole?: string | null): MatchInfo {
  if (!jobText || !jobText.trim()) {
    return { score: 0, label: "Low match" };
  }

  const textLower = jobText.toLowerCase();
  const keywords = getKeywordsForRole(requestedRole);
  
  // If no role-specific keywords, return low match
  if (keywords.length === 0) {
    return { score: 0, label: "Low match" };
  }

  const maxHits = keywords.length;
  let hits = 0;

  // Count distinct keywords that appear in the text
  for (const keyword of keywords) {
    if (textLower.includes(keyword.toLowerCase())) {
      hits++;
    }
  }

  // Compute score as percentage of keywords found
  const score = Math.round((hits / maxHits) * 100);

  // Derive label based on score
  let label: MatchInfo["label"];
  if (score >= 70) {
    label = "Strong match";
  } else if (score >= 40) {
    label = "Good match";
  } else if (score >= 20) {
    label = "Possible match";
  } else {
    label = "Low match";
  }

  return { score, label };
}

/**
 * Normalized job card type for consistent UI display
 */
export type JobCard = {
  kind: "direct_role" | "job_board_listing" | "template_or_guide";
  title: string;
  company: string;
  location: string;
  sourceDomain: string;
  snippet: string;
  matchLabel: string;
  matchInfo?: MatchInfo; // Computed match score and label
  hiringBadge: "Hiring" | "Maybe" | "Unknown";
  applyUrl: string;
  // Additional metadata for sorting/filtering
  resumeMatchScore?: number;
  missingSkills?: string[];
  originalCompany?: string; // Original company name from backend
  // Standardized display fields
  displayTitle: string;
  displayCompany: string;
  displayLocation?: string;
  // Posted pay range, e.g. "$150K – $250K". Only present when the posting stated one.
  salary?: string;
  // Calibrated match: a band a human can act on, plus why. Never a fabricated number.
  matchBand?: "strong" | "possible" | "stretch" | "unknown";
  matchProbability?: number;
  matchExplanation?: string;
  // Computed match score for easy access
  matchScore?: number;
  // Apify integration fields
  source?: "tavily" | "apify" | null; // Where the job was discovered
  ats?: "greenhouse" | "lever" | "ashby" | "workday" | null; // ATS system if detected
};

/**
 * Raw company data structure from backend (HiringCompany model)
 * Maps backend field names to frontend expectations
 */
export type RawCompanyData = {
  // Backend sends these fields from HiringCompany model
  company_name?: string;
  job_title?: string | null;
  job_url?: string | null;
  job_location?: string | null;
  blurb?: string | null;
  clean_company?: string | null;
  clean_title?: string | null;
  clean_snippet?: string | null;
  display_data?: {
    title?: string;
    company?: string;
    summary?: string;
    location?: string;
    source_tag?: string;
  } | null;
  
  // Posted pay range (backend HiringCompany.salary)
  salary?: string | null;
  // Calibrated match (backend HiringCompany)
  match_band?: "strong" | "possible" | "stretch" | "unknown" | null;
  match_probability?: number | null;
  match_explanation?: string | null;
  // Legacy fields (for backward compatibility)
  name?: string;
  city?: string | null;
  homepage?: string | null;
  homepage_url?: string | null;
  missing_skills?: string[];
  job_posting?: {
    url: string;
    title: string;
    snippet?: string | null;
    location?: string | null;
    company?: string | null;
    missing_skills?: string[];
    resume_match_score?: number;
    source?: "tavily" | "apify" | null;
    ats?: "greenhouse" | "lever" | "ashby" | "workday" | null;
    salary?: string | null;
  } | null;
  resume_match_score?: number;
  trust_score?: number;
  trust_label?: string;
  [key: string]: any; // Allow other fields
};

/**
 * Extract domain from URL
 */
function getDomainFromUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.hostname;
  } catch {
    return null;
  }
}

/**
 * Check if URL is from an ATS domain
 */
function isAtsUrl(url: string | null | undefined): boolean {
  const domain = getDomainFromUrl(url);
  if (!domain) return false;
  return ATS_DOMAINS.some((d) => domain === d || domain.endsWith(`.${d}`));
}

/**
 * Check if URL is from a job aggregator/board
 */
function isAggregatorUrl(url: string | null | undefined): boolean {
  const domain = getDomainFromUrl(url);
  if (!domain) return false;
  return JOB_SOURCE_DOMAINS.some((d) => domain === d || domain.endsWith(`.${d}`));
}

/**
 * Check if title looks like an aggregator/listing page
 */
function isListingTitle(title: string): boolean {
  const titleLower = title.toLowerCase();
  
  // Patterns that indicate listing pages
  const listingPatterns = [
    /^best\s+.+\s+jobs/i,
    /.+\s+jobs\s+in\s+/i,
    /top\s+.+\s+jobs/i,
    /\d+\+\s+.+\s+jobs/i,
    /.+\s+jobs?\s*$/i,
  ];
  
  return listingPatterns.some(pattern => pattern.test(title));
}

/**
 * Template/guide detection patterns
 */
const TEMPLATE_TITLE_PATTERNS = [
  "interview questions",
  "job description template",
  "job description [+202",
  "proven interview questions",
  "template]",
  "templates]",
  "best jobs in",
  "top 10 best",
  "guide to",
  "how to hire",
];

const TEMPLATE_DOMAINS = [
  "resources.workable.com",
  "blog.",   // e.g. blog.* domains
  "hiring guide",
];

/**
 * Strong detection for templates/guides based on title and URL patterns
 */
function looksLikeTemplateOrGuide(rawTitle: string, url: string): boolean {
  const t = (rawTitle || "").toLowerCase();
  const u = (url || "").toLowerCase();

  if (TEMPLATE_TITLE_PATTERNS.some(p => t.includes(p))) return true;
  if (TEMPLATE_DOMAINS.some(p => u.includes(p))) return true;

  return false;
}

/**
 * Check if title looks like a template/guide (legacy function, kept for compatibility)
 */
function isTemplateOrGuide(title: string): boolean {
  const titleLower = title.toLowerCase();
  
  const templateKeywords = [
    "job description",
    "template",
    "guide",
    "example",
    "sample",
    "how to write",
    "format",
    "example job",
  ];
  
  return templateKeywords.some(keyword => titleLower.includes(keyword));
}

/**
 * Clean job title by removing noise
 */
function cleanJobTitle(title: string): string {
  let cleaned = title.trim();
  
  // Remove location suffixes: " jobs in San Francisco, CA"
  cleaned = cleaned.replace(/\s+jobs\s+in\s+.*$/i, "");
  
  // Remove trailing "jobs" or "job openings"
  cleaned = cleaned.replace(/\s+jobs?\s*$/i, "");
  
  // Remove "Best " prefix
  cleaned = cleaned.replace(/^best\s+/i, "");
  
  // Remove "Top " prefix
  cleaned = cleaned.replace(/^top\s+/i, "");
  
  // Remove "Hiring: " prefix
  cleaned = cleaned.replace(/^hiring:\s*/i, "");

  // Remove leading numbers (e.g. "483 Remote Software Engineer")
  cleaned = cleaned.replace(/^\d+\s+/, "");

  // Remove "Remote" if it's at the start (redundant with location usually)
  cleaned = cleaned.replace(/^remote\s+/i, "");
  
  // Remove company name from title if it's at the start (e.g., "OpenAI - AI Engineer")
  cleaned = cleaned.replace(/^[^-]+-\s*/, "");
  
  return cleaned.trim();
}

/**
 * Extract company name from domain
 */
function extractCompanyFromDomain(url: string | null | undefined): string | null {
  const domain = getDomainFromUrl(url);
  if (!domain) return null;
  
  // Remove common prefixes
  const cleaned = domain
    .replace(/^www\./, "")
    .replace(/^jobs?\./, "")
    .replace(/^careers?\./, "");
  
  // Extract main domain name
  const parts = cleaned.split(".");
  if (parts.length >= 2) {
    return parts[parts.length - 2]; // Second-to-last part (e.g., "openai" from "jobs.openai.com")
  }
  
  return cleaned;
}

/**
 * Derive a human-friendly company name from URL domain
 */
function getCompanyNameFromUrl(url: string): string {
  const domain = getDomainFromUrl(url);
  if (!domain) return "Company";
  
  // Remove common prefixes
  const cleaned = domain
    .replace(/^www\./, "")
    .replace(/^jobs?\./, "")
    .replace(/^careers?\./, "")
    .replace(/^boards?\./, "");
  
  // Extract main domain name
  const parts = cleaned.split(".");
  let companyName = parts.length >= 2 ? parts[parts.length - 2] : cleaned;
  
  // Capitalize first letter of each word
  companyName = companyName
    .split(/[-._]/)
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
  
  return companyName || "Company";
}

/**
 * Convert string to title case (capitalize first letter of each word)
 */
function toTitleCase(str: string): string {
  return str
    .toLowerCase()
    .split(/\s+/)
    .map(word => {
      // Keep short words lowercase (a, an, the, of, etc.) except if first word
      const shortWords = ["a", "an", "the", "of", "and", "or", "but", "in", "on", "at", "to", "for", "with"];
      if (shortWords.includes(word) && word !== str.split(/\s+/)[0]) {
        return word;
      }
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(" ");
}

/**
 * Extract role from snippet using regex patterns
 */
function extractRoleFromSnippet(snippet: string): string | null {
  if (!snippet || !snippet.trim()) return null;
  
  // Take first 1-2 sentences (up to ~200 chars to catch most cases)
  const firstPart = snippet.substring(0, 200).trim();
  
  // Patterns to match roles in snippets
  const rolePatterns = [
    /is seeking (?:an|a) (.+?)\b/i,
    /is looking for (?:an|a) (.+?)\b/i,
    /we are hiring (?:an|a) (.+?)\b/i,
    /as (?:an|a) (.+?)(?:,\s*you will|,|\s+you will)/i,
    /looking for (?:an|a) (.+?)\b/i,
    /seeking (?:an|a) (.+?)\b/i,
  ];
  
  for (const pattern of rolePatterns) {
    const match = firstPart.match(pattern);
    if (match && match[1]) {
      let role = match[1].trim();
      
      // Clean up common trailing words/phrases
      role = role
        .replace(/\s*to join.*$/i, "")
        .replace(/\s*who.*$/i, "")
        .replace(/\s*to work.*$/i, "")
        .replace(/\s*to help.*$/i, "")
        .replace(/\s*,\s*$/, "")
        .replace(/\s+–\s*$/, "") // Remove trailing em dash
        .replace(/\s+—\s*$/, "") // Remove trailing em dash (different char)
        .replace(/\s+-\s*$/, "") // Remove trailing hyphen
        .trim();
      
      // Check length constraint: 5-60 chars
      if (role.length >= 5 && role.length <= 60) {
        return toTitleCase(role);
      }
    }
  }
  
  return null;
}

/**
 * Get role display name (e.g., "Backend Engineer" -> "Backend roles", "AI Engineer" -> "AI/ML roles")
 */
function getRoleDisplayName(role: string | null | undefined): string {
  if (!role) return "roles";
  
  const roleLower = role.toLowerCase().trim();
  
  // Handle special cases first
  if (roleLower.includes("ai") || roleLower.includes("artificial intelligence")) {
    return "AI/ML roles";
  }
  if (roleLower.includes("ml") || roleLower.includes("machine learning")) {
    return "Machine Learning roles";
  }
  if (roleLower.includes("full stack") || roleLower.includes("full-stack") || roleLower.includes("fullstack")) {
    return "Full-Stack roles";
  }
  if (roleLower.includes("frontend") || roleLower.includes("front-end")) {
    return "Frontend roles";
  }
  if (roleLower.includes("devops") || roleLower.includes("dev ops")) {
    return "DevOps roles";
  }
  if (roleLower.includes("cybersecurity") || roleLower.includes("cyber security")) {
    return "Cybersecurity roles";
  }
  if (roleLower.includes("data engineer")) {
    return "Data Engineer roles";
  }
  if (roleLower.includes("data analyst")) {
    return "Data Analyst roles";
  }
  if (roleLower.includes("product manager") || roleLower === "pm") {
    return "Product Manager roles";
  }
  if (roleLower.includes("software architect") || roleLower.includes("software arch")) {
    return "Software Architect roles";
  }
  if (roleLower.includes("java developer") || (roleLower.includes("java") && roleLower.includes("developer"))) {
    return "Java Developer roles";
  }
  if (roleLower.includes("mobile developer") || roleLower.includes("mobile dev")) {
    return "Mobile Developer roles";
  }
  if (roleLower.includes("blockchain developer") || roleLower.includes("blockchain dev")) {
    return "Blockchain Developer roles";
  }
  if (roleLower.includes("cloud engineer")) {
    return "Cloud Engineer roles";
  }
  
  // Extract main role type (e.g., "Backend Engineer" -> "Backend")
  // Try to find the main keyword before "Engineer", "Developer", etc.
  const roleKeywords = ["engineer", "developer", "architect", "analyst", "scientist", "manager"];
  for (const keyword of roleKeywords) {
    if (roleLower.includes(keyword)) {
      const parts = roleLower.split(keyword);
      const prefix = parts[0].trim();
      if (prefix) {
        // Clean up common prefixes and suffixes
        const cleaned = prefix
          .replace(/^(senior|junior|lead|principal|staff|sr\.|sr|jr\.|jr)\s+/i, "")
          .replace(/\s+(senior|junior|lead|principal|staff)$/i, "")
          .trim();
        if (cleaned) {
          return `${toTitleCase(cleaned)} roles`;
        }
      }
    }
  }
  
  // Fallback: use the full role name (cleaned)
  const cleaned = role
    .replace(/^(senior|junior|lead|principal|staff|sr\.|sr|jr\.|jr)\s+/i, "")
    .trim();
  return `${toTitleCase(cleaned)} roles`;
}

/**
 * Get display title for job card with priority logic
 */
function getDisplayTitle(params: {
  rawTitle?: string | null;
  snippet: string;
  url: string;
  requestedRole?: string | null;
}): string {
  const { rawTitle, snippet, url, requestedRole } = params;
  
  // Priority 1: Try to extract role from snippet
  const roleFromSnippet = extractRoleFromSnippet(snippet);
  if (roleFromSnippet) {
    return roleFromSnippet;
  }
  
  // Priority 2: Check if rawTitle is noisy/missing
  const rawTitleLower = rawTitle?.toLowerCase().trim() || "";
  const isNoisyTitle = 
    !rawTitle ||
    rawTitle.length < 4 ||
    rawTitleLower.includes("job application") ||
    rawTitleLower.includes("jobs in") ||
    rawTitleLower.includes("job description") ||
    rawTitleLower.includes("template") ||
    rawTitleLower.startsWith("best ") ||
    rawTitleLower.includes("van, fuel & insurance") ||
    rawTitleLower === "application";
  
  if (isNoisyTitle) {
    // Derive company name from URL
    const companyName = getCompanyNameFromUrl(url);
    const roleDisplayName = getRoleDisplayName(requestedRole);
    return `${roleDisplayName} at ${companyName}`;
  }
  
  // Priority 3: Clean and use rawTitle
  let cleaned = rawTitle.trim();
  
  // Remove trailing "jobs in ..." segments
  cleaned = cleaned.replace(/\s+jobs?\s+in\s+.*$/i, "");
  
  // Remove prefixes
  cleaned = cleaned.replace(/^job\s+application\s+for\s*/i, "");
  cleaned = cleaned.replace(/^job\s+description\s*[–—-]\s*/i, "");
  
  // Apply title case
  cleaned = toTitleCase(cleaned.trim());
  
  return cleaned;
}

/**
 * Extract display title with smart handling for templates/guides
 */
function getDisplayTitleValue(params: {
  rawTitle?: string | null;
  snippet: string;
  url: string;
  requestedRole?: string | null;
  kind: JobCard["kind"];
  companyName: string; // Added companyName parameter
}): string {
  const { rawTitle, snippet, url, requestedRole, kind, companyName } = params;
  
  // For templates/guides, keep original title but clean it
  if (kind === "template_or_guide") {
    let cleaned = (rawTitle || "").trim();
    // Strip noisy suffixes in square brackets like [+answers]
    cleaned = cleaned.replace(/\s*\[.*?\]\s*$/g, "");
    return cleaned || "Resource";
  }
  
  // For job board listings that look like lists, shorten them
  if (kind === "job_board_listing") {
    const titleLower = (rawTitle || "").toLowerCase();
    if (titleLower.includes("top") || titleLower.includes("best") || titleLower.includes("jobs in")) {
      // Try to extract city from title or use requested role
      const cityMatch = rawTitle?.match(/(?:in|at)\s+([^,]+)/i);
      const city = cityMatch ? cityMatch[1].trim() : null;
      const rolePart = requestedRole ? `${requestedRole} roles` : "Tech jobs";
      return city ? `${rolePart} in ${city} (job board)` : `${rolePart} (job board)`;
    }
  }
  
  // Get base title
  const title = getDisplayTitle({
    rawTitle,
    snippet,
    url,
    requestedRole,
  });

  // If the title is generic (e.g. "AI Engineer") and matches the requested role exactly,
  // append the company name to make it distinct.
  // e.g. "AI Engineer" -> "AI Engineer at Anthropic"
  if (requestedRole && title.toLowerCase() === requestedRole.toLowerCase()) {
    // Only append if we have a valid company name (not "Unknown" or "via Indeed")
    const isGenericCompany = [
      "via indeed", "via glassdoor", "unknown company", "hiring company", 
      "indeed", "glassdoor", "ziprecruiter", "linkedin", "google", "simplyhired"
    ].some(
      gc => companyName.toLowerCase().includes(gc)
    );
    
    if (!isGenericCompany && companyName && companyName.length < 30) {
       return `${title} at ${companyName}`;
    }
  }

  return title;
}

/**
 * Extract company name from job board listing snippets/titles
 * Aggregator sites often have company names in the snippet or title
 */
function extractCompanyFromJobBoardListing(title: string, snippet: string, url: string): string | null {
  const combined = `${title} ${snippet}`;
  
  // Pattern 1: "Company Name | Role" or "Company Name - Role"
  const titlePattern = /^([A-Z][a-zA-Z0-9\s&.-]+?)\s*[–—|-]\s*/;
  const titleMatch = title.match(titlePattern);
  if (titleMatch && titleMatch[1]) {
    const company = titleMatch[1].trim();
    // Filter out common false positives
    if (company.length > 2 && company.length < 50 && 
        !company.toLowerCase().includes("job") &&
        !company.toLowerCase().includes("hiring")) {
      return company;
    }
  }
  
  // Pattern 2: Look for "at Company" or "Company is hiring" in snippet
  const snippetPatterns = [
    /at\s+([A-Z][a-zA-Z0-9\s&.-]+?)(?:\s|$|,|\.)/,
    /([A-Z][a-zA-Z0-9\s&.-]+?)\s+is\s+hiring/i,
    /([A-Z][a-zA-Z0-9\s&.-]+?)\s+\|\s+[A-Z]/,
  ];
  
  for (const pattern of snippetPatterns) {
    const match = combined.match(pattern);
    if (match && match[1]) {
      const company = match[1].trim();
      // Filter out false positives
      if (company.length > 2 && company.length < 50 &&
          !company.toLowerCase().includes("indeed") &&
          !company.toLowerCase().includes("glassdoor") &&
          !company.toLowerCase().includes("ziprecruiter") &&
          !company.toLowerCase().includes("job") &&
          !company.toLowerCase().includes("search")) {
        return company;
      }
    }
  }
  
  // Pattern 3: Extract from URL if it's a company-specific page
  // e.g., "indeed.com/viewjob?jk=abc&cmp=CompanyName"
  const urlMatch = url.match(/[?&]cmp=([^&]+)/i);
  if (urlMatch && urlMatch[1]) {
    const company = decodeURIComponent(urlMatch[1]).replace(/\+/g, ' ').trim();
    if (company.length > 2 && company.length < 50) {
      return company;
    }
  }
  
  return null;
}

/**
 * Extract display company name
 */
function getDisplayCompanyValue(params: {
  companyName?: string | null;
  url: string;
  rawTitle?: string | null;
  rawSnippet?: string | null;
}): string {
  const { companyName, url, rawTitle, rawSnippet } = params;
  
  // Prefer company_name from backend, UNLESS it looks like an error/aggregator
  if (companyName && companyName.trim()) {
    const nameLower = companyName.toLowerCase().trim();
    const invalidNames = ["indeed", "glassdoor", "ziprecruiter", "linkedin", "company", "unknown company", "hiring", "software engineer", "engineer", "developer"];
    
    // Check if it's a known invalid name
    if (invalidNames.includes(nameLower)) {
      // Fall through to other extraction methods
    } 
    // Check if it matches the title exactly (often an extraction error)
    else if (rawTitle && nameLower === rawTitle.toLowerCase().trim()) {
      // Fall through
    }
    else {
      return companyName.trim();
    }
  }
  
  // Try to extract from job board listing
  if (rawSnippet || rawTitle) {
    const extracted = extractCompanyFromJobBoardListing(
      rawTitle || "",
      rawSnippet || "",
      url
    );
    if (extracted) {
      return extracted;
    }
  }
  
  // Fallback: try to infer from page title by splitting on - or |
  if (rawTitle) {
    const parts = rawTitle.split(/[–—\-|]/).map(p => p.trim());
    if (parts.length > 1 && parts[0].length > 2 && parts[0].length < 50) {
      // First part might be company name
      const candidate = parts[0];
      // Filter out common false positives
      if (!candidate.toLowerCase().includes("job") &&
          !candidate.toLowerCase().includes("hiring")) {
        return candidate;
      }
    }
  }
  
  // Last resort: extract from domain
  const domainCompany = extractCompanyFromDomain(url);
  if (domainCompany) {
    return toTitleCase(domainCompany);
  }
  
  // Never leave blank
  return "Unknown company";
}

/**
 * Extract display location
 */
function getDisplayLocationValue(params: {
  location?: string | null;
  city?: string | null;
  searchCity?: string | null;
}): string | undefined {
  const { location, city, searchCity } = params;
  
  // Prefer explicit location field if present
  if (location && location.trim() && location !== "Location not specified") {
    return location.trim();
  }
  
  // Else, try to extract city from the search city parameter
  if (city && city.trim()) {
    return city.trim();
  }
  
  // Use search city if available
  if (searchCity && searchCity.trim()) {
    // Extract city name from "City, ST" format
    const cityMatch = searchCity.match(/^([^,]+)/);
    return cityMatch ? cityMatch[1].trim() : searchCity.trim();
  }
  
  return undefined;
}

/**
 * Extract meaningful role description from snippet
 * Focuses on what the role is about, not aggregator noise
 */
function extractRoleDescription(snippet: string): string | null {
  if (!snippet || !snippet.trim()) return null;
  
  // Look for role description patterns
  const rolePatterns = [
    // "We are seeking a [role] to..."
    /(?:we\s+are\s+seeking|looking\s+for|hiring)\s+(?:an|a)?\s*([^.!?]{20,150}?)(?:\.|$|to\s+join|who)/i,
    // "Design and develop..." (action-oriented descriptions)
    /(?:design|develop|build|create|implement|work\s+on)\s+([^.!?]{20,150}?)(?:\.|$)/i,
    // "As a [role], you will..."
    /as\s+(?:an|a)\s+([^.!?]{15,120}?)(?:,\s*you|\.|$)/i,
    // "Join our team to..."
    /join\s+our\s+team\s+to\s+([^.!?]{20,150}?)(?:\.|$)/i,
  ];
  
  for (const pattern of rolePatterns) {
    const match = snippet.match(pattern);
    if (match && match[1]) {
      let desc = match[1].trim();
      // Clean up common prefixes/suffixes
      desc = desc.replace(/^(?:a|an|the)\s+/i, "");
      desc = desc.replace(/\s+to\s+(?:join|work|help).*$/i, "");
      if (desc.length >= 20 && desc.length <= 200) {
        return desc;
      }
    }
  }
  
  return null;
}

/**
 * Clean and truncate snippet - remove noise, numbers, aggregator boilerplate
 * Returns a professional 2-line summary focused on role description
 */
function cleanSnippet(snippet: string | null | undefined, maxLength: number = 200): string {
  if (!snippet || !snippet.trim()) return "";
  
  let cleaned = snippet.trim();
  
  // First, try to extract meaningful role description
  const roleDesc = extractRoleDescription(cleaned);
  if (roleDesc) {
    cleaned = roleDesc;
  } else {
    // If no role description found, clean the original snippet
    
    // Remove job count patterns: #549, 1288 jobs, etc.
    cleaned = cleaned.replace(/#\d+\s*/g, "");
    cleaned = cleaned.replace(/\d+\s+(jobs?|positions?|openings?)\s+(available|in)/gi, "");
    cleaned = cleaned.replace(/\d+\s+(Ai|AI|Machine Learning|Software|Generative)\s+engineer\s+jobs/gi, "");
    
    // Remove location repetition patterns: "Austin, TX + machine learning engineer jobs in Austin, TX"
    cleaned = cleaned.replace(/([A-Z][a-z]+,\s*[A-Z]{2})\s*\+\s*[^.]*jobs?\s+in\s+\1/gi, "$1");
    
    // Remove aggregator noise
    const aggregatorNoise = [
      /Visit\s+Indeed\s+for\s+employers/gi,
      /Apply\s+to\s+[^.!]*\s+and\s+more!/gi,
      /on\s+Indeed\.com/gi,
      /on\s+Glassdoor/gi,
      /jobs\s+available\s+in/gi,
      /jobs\s+in\s+[^.!]*on\s+/gi,
      /Profile\s+insights/gi,
      /Find\s+out\s+how\s+your\s+skills/gi,
      /Robotics\s+Technologies\s+jobs/gi,
      /Autonomize\s+Al\s+jobs/gi,
      /also\s+searched\s+for/gi,
      /in\s+[A-Z][a-z]+,\s*[A-Z]{2}\s+also\s+searched/gi,
      /Apply\s+to\s+.*$/i, // "Apply to Software Engineer..."
      /available\s+in\s+.*$/i, // "available in South Austin..."
      /Browse\s+\d+\s+.*jobs/i, // "Browse 60 ... jobs"
      /Salary\s+Search:/i, // "Salary Search: ..."
      /Jobs,?\s+Employment\s+in\s+/i, // "Jobs, Employment in ..."
      /Ai\s+Engineers\s+Jobs/i,
    ];
    
    for (const pattern of aggregatorNoise) {
      cleaned = cleaned.replace(pattern, "");
    }
    
    // Remove common marketing fluff patterns
    const fluffPatterns = [
      /^hiring\s*[:-]?\s*/i,
      /^we're\s+hiring\s*[:-]?\s*/i,
      /^join\s+us\s*[:-]?\s*/i,
      /\s*apply\s+now\s*$/i,
      /\s*learn\s+more\s*$/i,
    ];
    
    for (const pattern of fluffPatterns) {
      cleaned = cleaned.replace(pattern, "");
    }
    
    // Remove redundant phrases
    cleaned = cleaned.replace(/\s+jobs?\s+(available|in|on)/gi, "");
    cleaned = cleaned.replace(/\s+on\s+(Indeed|Glassdoor|Dice)\.com/gi, "");
    
    // Extract first 2 meaningful sentences (professional summary)
    const sentences = cleaned.split(/[.!?]+/).filter(s => s.trim().length > 0);
    const meaningfulSentences: string[] = [];
    
    for (const sent of sentences) {
      const trimmed = sent.trim();
      // Skip very short sentences, noise, or sentences starting with numbers or #
      if (trimmed.length > 20 && 
          !/^\d+/.test(trimmed) && 
          !trimmed.startsWith("#") &&
          !trimmed.toLowerCase().includes("also searched")) {
        meaningfulSentences.push(trimmed);
        if (meaningfulSentences.length >= 2) {
          break;
        }
      }
    }
    
    if (meaningfulSentences.length > 0) {
      cleaned = meaningfulSentences.join(". ") + ".";
    } else {
      // Fallback: take first 200 chars and clean
      cleaned = cleaned.substring(0, 200).trim();
      // Remove trailing incomplete words
      const lastSpace = cleaned.lastIndexOf(" ");
      if (lastSpace > 150) {
        cleaned = cleaned.substring(0, lastSpace);
      }
    }
  }
  
  // If cleaned snippet is still too short/empty, try to construct a generic one
  if (cleaned.length < 20) {
    // We won't return a generic "View details" here because JobCard handles hiding empty snippets.
    // Returning empty string lets JobCard decide whether to hide it or show a fallback.
    return "";
  }
  
  // Remove repeated text (simple heuristic: if first 50 chars appear again)
  if (cleaned.length > 100) {
    const first50 = cleaned.substring(0, 50);
    const nextOccurrence = cleaned.indexOf(first50, 50);
    if (nextOccurrence > 0 && nextOccurrence < cleaned.length * 0.7) {
      cleaned = cleaned.substring(0, nextOccurrence);
    }
  }
  
  // Final cleanup: remove extra whitespace
  cleaned = cleaned.replace(/\s+/g, " ").trim();
  
  // Truncate to max length for 2-line display
  if (cleaned.length > maxLength) {
    cleaned = cleaned.substring(0, maxLength).trim();
    // Don't cut in the middle of a word if possible
    const lastSpace = cleaned.lastIndexOf(" ");
    if (lastSpace > maxLength * 0.8) {
      cleaned = cleaned.substring(0, lastSpace);
    }
    cleaned += "…";
  }
  
  return cleaned.trim();
}

/**
 * Normalize raw company data with job posting into JobCard format
 * Handles both legacy format (job_posting object) and new HiringCompany format
 */
export function normalizeJobCard(
  company: RawCompanyData,
  requestedRole?: string | null
): JobCard | null {
  // === STEP 1: Extract URL - support both formats ===
  // New format: job_url directly on company
  // Legacy format: job_posting.url
  const url = company.job_url || company.job_posting?.url;
  if (!url) {
    return null;
  }
  
  // === STEP 2: Use display_data if available (backend already cleaned) ===
  const displayData = company.display_data;
  
  // Extract title - prefer display_data > clean_title > job_title > job_posting.title
  const title = displayData?.title || company.clean_title || company.job_title || company.job_posting?.title || "";
  
  // Extract snippet/summary - prefer display_data > clean_snippet > blurb > job_posting.snippet
  const snippet = displayData?.summary || company.clean_snippet || company.blurb || company.job_posting?.snippet || "";
  
  // Extract company name - prefer display_data > clean_company > company_name > name
  const companyName = displayData?.company || company.clean_company || company.company_name || company.name || "";
  
  // Extract location - prefer display_data > job_location > city
  const locationFromBackend = displayData?.location || company.job_location || company.city || "";
  
  // For backward compatibility, create a synthetic job object
  const job = company.job_posting || {
    url: url,
    title: title,
    snippet: snippet,
    location: locationFromBackend,
    company: companyName,
  };
  
  // Determine kind based on URL and title - use strong detection first
  let kind: JobCard["kind"];
  let hiringBadge: JobCard["hiringBadge"];
  
  if (looksLikeTemplateOrGuide(title, url)) {
    kind = "template_or_guide";
    hiringBadge = "Unknown";
  } else if (company.job_posting && company.job_posting.url) {
    // If we have a verified job posting with URL, it's confirmed hiring
    kind = isAtsUrl(url) ? "direct_role" : "job_board_listing";
    hiringBadge = "Hiring";
  } else if (isAtsUrl(url)) {
    kind = "direct_role";
    hiringBadge = "Hiring";
  } else if (isAggregatorUrl(url)) {
    // Treat job boards as hiring too (they link to actual jobs)
    kind = "job_board_listing";
    hiringBadge = "Hiring";
  } else {
    kind = "job_board_listing";
    hiringBadge = "Unknown";  // Only unknown if truly unclear
  }
  
  // Extract source domain
  const sourceDomain = getDomainFromUrl(url) || "Unknown";
  
  // Determine title and company based on kind
  let normalizedTitle: string;
  let normalizedCompany: string;
  
  // Use getDisplayTitle for all kinds - it handles extraction, cleaning, and fallbacks
  const rawSnippet = job.snippet || "";
  normalizedTitle = getDisplayTitle({
    rawTitle: title,
    snippet: rawSnippet,
    url: url,
    requestedRole: requestedRole,
  });
  
  // === STEP 3: Use backend-cleaned values if available ===
  // If backend already cleaned the data (display_data exists), use those values directly
  if (displayData?.company && displayData.company !== "Company via" && !displayData.company.startsWith("Company via")) {
    normalizedCompany = displayData.company;
  } else if (kind === "direct_role") {
    // Use company name if available, otherwise try to extract from domain
    normalizedCompany = companyName || extractCompanyFromDomain(url) || sourceDomain;
  } else if (kind === "job_board_listing") {
    // For aggregator listings, try to extract company name from snippet/title
    // Fallback to source domain only if we can't find a company name
    const extractedCompany = extractCompanyFromJobBoardListing(title, snippet, url);
    normalizedCompany = extractedCompany || companyName || extractCompanyFromDomain(url) || sourceDomain;
  } else {
    // template_or_guide: use source domain as company
    normalizedCompany = sourceDomain;
  }
  
  // Use backend-cleaned title if available
  if (displayData?.title) {
    normalizedTitle = displayData.title;
  }
  
  // Location - prefer backend's cleaned location
  const location = locationFromBackend || company.city || "Location not specified";
  
  // Clean snippet - prefer backend's cleaned summary
  const normalizedSnippet = displayData?.summary || cleanSnippet(snippet);
  
  // Compute match info from job text (title + company + snippet) with requested role
  const jobText = `${normalizedTitle} ${normalizedCompany} ${normalizedSnippet}`.trim();
  const matchInfo = computeMatchInfo(jobText, requestedRole);
  
  // Build match label with role and match info
  let matchLabel = "";
  if (requestedRole) {
    if (matchInfo.score >= 10) {
      // Show match label for scores >= 10
      matchLabel = `Matched for ${requestedRole} – ${matchInfo.label}`;
    } else {
      // Hide or show subtle label for very low scores
      matchLabel = ""; // Hide completely for very low scores
    }
  }
  
  // Compute display fields - prefer backend's display_data if available
  let displayCompany: string;
  let displayTitle: string;
  let displayLocation: string | undefined;
  
  if (displayData) {
    // Backend already cleaned the data - use it directly
    displayCompany = displayData.company || normalizedCompany;
    displayTitle = displayData.title || normalizedTitle;
    // Clean up location - remove "See job posting" fallback, strip emoji prefix for cleaner display
    let backendLocation = displayData.location || location;
    if (backendLocation && backendLocation.includes("See job posting")) {
      backendLocation = undefined; // Let frontend handle fallback
    }
    // Remove emoji prefix if present (📍 or 🌐) - frontend adds its own icon
    if (backendLocation) {
      backendLocation = backendLocation.replace(/^[^\w\s]+/u, "").trim();
    }
    displayLocation = backendLocation || location;
  } else {
    // Fall back to frontend extraction
    displayCompany = getDisplayCompanyValue({
      companyName: companyName || company.name,
      url: url,
      rawTitle: title,
      rawSnippet: rawSnippet,
    });

    displayTitle = getDisplayTitleValue({
      rawTitle: title,
      snippet: rawSnippet,
      url: url,
      requestedRole: requestedRole,
      kind: kind,
      companyName: displayCompany,
    });
    
    displayLocation = getDisplayLocationValue({
      location: location,
      city: company.city,
      searchCity: undefined,
    });
  }
  
  // Detect ATS from URL if not provided by backend
  let detectedAts: JobCard["ats"] = job.ats || null;
  if (!detectedAts && url) {
    const urlLower = url.toLowerCase();
    if (urlLower.includes("greenhouse.io") || urlLower.includes("boards.greenhouse")) {
      detectedAts = "greenhouse";
    } else if (urlLower.includes("lever.co") || urlLower.includes("jobs.lever")) {
      detectedAts = "lever";
    } else if (urlLower.includes("ashbyhq.com") || urlLower.includes("jobs.ashby")) {
      detectedAts = "ashby";
    } else if (urlLower.includes("workday.com") || urlLower.includes("myworkdayjobs")) {
      detectedAts = "workday";
    }
  }

  // Filter out clearly non-software engineering roles
  const _titleForFilter = (title || "").toLowerCase();
  const _excludePatterns = [
    "mechanical", "civil engineer", "electrical engineer", "chemical engineer",
    "biomedical", "manufacturing engineer", "hardware systems", "facilities",
    "structural engineer", "industrial engineer", "process engineer",
    "instrumentation", "petroleum", "nuclear", "aerospace", "marine",
  ];
  for (const p of _excludePatterns) {
    if (_titleForFilter.includes(p)) return null;
  }

  return {
    kind,
    title: normalizedTitle,
    company: normalizedCompany,
    location,
    sourceDomain,
    snippet: normalizedSnippet,
    matchLabel,
    matchInfo,
    hiringBadge,
    applyUrl: url,
    resumeMatchScore: company.resume_match_score ?? job.resume_match_score,
    missingSkills: company.missing_skills || job.missing_skills || [],
    originalCompany: company.name,
    // Display fields
    displayTitle,
    displayCompany,
    displayLocation,
    // Posted pay range (only when the backend found a real one)
    salary: company.salary || company.job_posting?.salary || undefined,
    // Calibrated match — only when the backend actually assessed it
    matchBand: company.match_band ?? undefined,
    matchProbability: company.match_probability ?? undefined,
    matchExplanation: company.match_explanation ?? undefined,
    // Computed match score for easy access
    matchScore: company.resume_match_score ?? job.resume_match_score ?? matchInfo.score,
    // Apify integration fields
    source: job.source || null,
    ats: detectedAts,
  };
}

/**
 * Sort job cards by match score descending, then by kind, then by resume match score
 */
export function sortJobCards(cards: JobCard[]): JobCard[] {
  const kindOrder: Record<JobCard["kind"], number> = {
    direct_role: 0,
    job_board_listing: 1,
    template_or_guide: 2,
  };
  
  return [...cards].sort((a, b) => {
    // First sort by match score (descending) - strongest matches first
    const aScore = a.matchInfo?.score || 0;
    const bScore = b.matchInfo?.score || 0;
    if (aScore !== bScore) {
      return bScore - aScore;
    }
    
    // Then by kind
    const kindDiff = kindOrder[a.kind] - kindOrder[b.kind];
    if (kindDiff !== 0) return kindDiff;
    
    // Then by resume match score (if available)
    if (a.resumeMatchScore && b.resumeMatchScore) {
      return b.resumeMatchScore - a.resumeMatchScore;
    }
    if (a.resumeMatchScore) return -1;
    if (b.resumeMatchScore) return 1;
    
    // Finally by company name
    return a.company.localeCompare(b.company);
  });
}

/**
 * Group job cards by kind
 */
export function groupJobCards(cards: JobCard[]): {
  directRoles: JobCard[];
  listings: JobCard[];
  templates: JobCard[];
} {
  return {
    directRoles: cards.filter(c => c.kind === "direct_role"),
    listings: cards.filter(c => c.kind === "job_board_listing"),
    templates: cards.filter(c => c.kind === "template_or_guide"),
  };
}

