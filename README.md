# Agentception - AI-Powered Job Search Assistant

## 🎯 Project Overview

**Agentception** is a sophisticated multi-agent AI system designed to automate and personalize the job search process for AI/Software Engineers. The system combines company discovery, profile matching, and personalized outreach email generation into a seamless workflow.

### Key Features
- **Company Discovery**: Finds relevant companies using Exa.ai search across multiple platforms (Y Combinator, Wellfound, Product Hunt, TechCrunch, Crunchbase)
- **Role-Aware Matching**: Matches companies to specific roles (AI Engineer, Full-Stack Developer, Data Analyst, etc.) using keyword and value proposition analysis
- **Resume Integration**: Parses PDF resumes and integrates content into personalized outreach
- **Enhanced Research**: Gathers company intelligence (funding, tech stack, recent news) for better targeting
- **Personalized Outreach**: Generates tailored emails using DeepSeek LLM with company-specific hooks and resume highlights
- **Real-time Streaming**: Live timeline updates via Server-Sent Events (SSE)
- **Modern UI**: React/Next.js frontend with Tailwind CSS design system and Framer Motion animations

## 🏗️ Architecture

### Backend (`server/`)
- **FastAPI** application with async/await support
- **Multi-Agent System**: RAG Agent → Enhanced Research Agent → Writer Agent
- **Memory Management**: In-memory state store with persistent SQLite for saved items
- **External APIs**: Exa.ai (search), DeepSeek (LLM), Google Maps (geocoding)
- **PDF Processing**: Multi-library support (PyMuPDF, pypdf, pdfplumber) with graceful fallbacks

### Frontend (`ui/`)
- **Next.js 13** with TypeScript
- **Tailwind CSS** design system with custom components
- **Framer Motion** animations
- **Real-time Updates** via EventSource/SSE
- **Responsive Design** with mobile-first approach

### Key Components

#### 1. RAG Agent (`server/agents/rag_companies.py`)
- Discovers companies using role-aware Exa search
- Multi-role search capability (searches related roles for broader coverage)
- Geocoding integration for location-based filtering
- Resume parsing and integration
- Builds comprehensive RAG document for downstream agents

#### 2. Enhanced Research Agent (`server/agents/enhanced_research_agent.py`)
- Gathers multi-source intelligence: Recent News, Tech Stack, Funding, Culture, Growth Metrics
- Parallel processing with fault tolerance
- Credit optimization with configurable intelligence types
- Structured company intelligence output

#### 3. Writer Agent (`server/agents/writer_outreach.py`)
- Generates personalized outreach emails using DeepSeek LLM
- Company-specific research integration
- Resume content merging
- Professional email formatting with subjects and mailto links

#### 4. UI Components (`ui/components/`)
- **Design System**: Button, Input, Select, Card, Skeleton, Spinner components
- **Layout**: AppShell with animated liquid background
- **Timeline**: Real-time progress tracking with SSE
- **Results**: Structured display of companies and generated emails

## 🚀 Getting Started

### Prerequisites
- **Python 3.11+** with virtual environment support
- **Node.js 18+** with npm
- **API Keys**: Exa.ai, DeepSeek, Google Maps (optional)

### Installation

1. **Clone and Setup Environment**
```bash
git clone https://github.com/arun3676/agentception.git
cd agentception
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

2. **Install Backend Dependencies**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Create `requirements.txt` in project root:
```txt
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.5.0
httpx>=0.25.0
python-multipart>=0.0.6
python-dotenv>=1.0.0
PyMuPDF>=1.26.0
pypdf>=5.5.0
pdfplumber>=0.11.0
asyncio
sqlite3
```

3. **Install Frontend Dependencies**
```bash
cd ui
npm install
```

4. **Environment Configuration**
Create `.env` file in project root:
```env
EXA_API_KEY=your_exa_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
GOOGLE_MAPS_KEY=your_google_maps_key_here
DEBUG_DISCOVERY=true
DOMAIN_FILTER_ENABLED=true
MIN_URLS_FOR_FILTERED_PASS=6
EXA_MAX_CONCURRENCY=1
```

### Running the Application

#### Development Mode

1. **Start Backend Server**
```bash
# From project root
.venv\Scripts\python.exe -m uvicorn server.app:app --reload --host 0.0.0.0 --port 8000
```

2. **Start Frontend Server**
```bash
# From ui/ directory
cd ui
npm run dev
```

3. **Access Application**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

#### Production Deployment

##### Option 1: Docker Deployment (Recommended)

1. **Create Dockerfile** in project root:
```dockerfile
FROM node:18-alpine AS frontend-builder
WORKDIR /app/ui
COPY ui/package*.json ./
RUN npm ci --only=production
COPY ui/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server/ ./server/
COPY --from=frontend-builder /app/ui/out ./ui/out

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app
ENV BACKEND_URL=http://localhost:8000

# Start the application
CMD ["python", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

2. **Create docker-compose.yml**:
```yaml
version: '3.8'
services:
  agentception:
    build: .
    ports:
      - "8000:8000"
    environment:
      - EXA_API_KEY=${EXA_API_KEY}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - GOOGLE_MAPS_KEY=${GOOGLE_MAPS_KEY}
      - DEBUG_DISCOVERY=false
      - DOMAIN_FILTER_ENABLED=true
      - EXA_MAX_CONCURRENCY=2
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

3. **Build and Deploy**:
```bash
docker-compose up -d
```

##### Option 2: Manual Production Setup

1. **Build Frontend**:
```bash
cd ui
npm run build
npm run export  # For static export
```

2. **Configure Production Server**:
```bash
# Install production dependencies
pip install gunicorn

# Create production startup script
echo '#!/bin/bash
export PYTHONPATH=/path/to/Agentception
cd /path/to/Agentception
gunicorn server.app:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000' > start.sh
chmod +x start.sh
```

3. **Nginx Configuration** (optional):
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /static/ {
        alias /path/to/Agentception/ui/out/;
    }
}
```

##### Option 3: Cloud Deployment (AWS/GCP/Azure)

1. **AWS Elastic Beanstalk**:
```bash
# Create .ebextensions/python.config
option_settings:
  aws:elasticbeanstalk:container:python:
    WSGIPath: server.app:app
  aws:elasticbeanstalk:environment:proxy:staticfiles:
    /static: ui/out

# Deploy
eb init
eb create production
eb deploy
```

2. **Google Cloud Run**:
```bash
# Build and push to Container Registry
gcloud builds submit --tag gcr.io/PROJECT-ID/agentception

# Deploy to Cloud Run
gcloud run deploy --image gcr.io/PROJECT-ID/agentception --platform managed
```

3. **Azure Container Instances**:
```bash
# Build and push to Azure Container Registry
az acr build --registry myregistry --image agentception:latest .

# Deploy to Container Instance
az container create --resource-group myResourceGroup --name agentception --image myregistry.azurecr.io/agentception:latest
```

## 📋 Usage Workflow

### Basic Workflow
1. **Enter Location**: City name (e.g., "San Francisco", "Austin", "New York")
2. **Select Role**: Choose from predefined roles or use default "AI Engineer"
3. **Upload Resume** (Optional): PDF file for personalized content
4. **Run RAG**: Discovers and analyzes companies
5. **Generate Emails**: Creates personalized outreach emails

### Advanced Features
- **Multi-Role Search**: Automatically searches related roles for broader company coverage
- **Enhanced Research**: Gathers detailed company intelligence (configurable)
- **Credit Optimization**: Reduced API calls while maintaining quality
- **Real-time Timeline**: Live progress updates with detailed logging

## 🔧 API Endpoints

### Core Endpoints
- `POST /rag/companies` - Company discovery and analysis
- `POST /writer/outreach` - Email generation
- `POST /upload/resume` - Resume parsing and storage
- `GET /results/{run_id}` - Retrieve workflow results
- `GET /timeline/{run_id}` - SSE timeline stream

### Debug Endpoints
- `GET /debug/pdf` - PDF library availability check
- `GET /debug/fitz` - PyMuPDF import diagnostics

### Data Endpoints
- `POST /save/add` - Save companies/results
- `GET /save/list` - Retrieve saved items

## 📊 Data Models

### Company Intelligence (`CompanyIntel`)
```python
{
    "name": str,
    "homepage": str,
    "source_url": str,
    "blurb": str,
    "city": str,
    "tags": List[str],
    "contact_hint": str,
    "score": float
}
```

### RAG Document Structure
```python
{
    "city": str,
    "role": str,
    "role_profile": {
        "keywords": List[str],
        "value_props": List[str]
    },
    "companies": List[CompanyIntel],
    "resume_excerpt": str,
    "search_metadata": dict
}
```

### Generated Email Structure
```python
{
    "company": str,
    "subject": str,
    "body": str,
    "mailto": str
}
```

## 🎨 UI/UX Features & CSS Architecture

### Design System Overview

The UI is built with a **modern dark theme** using **Tailwind CSS** with custom design tokens and **Framer Motion** for animations. The design emphasizes readability, accessibility, and a premium feel.

#### Color Palette & Theme System

```css
/* Custom CSS Variables (ui/styles/globals.css) */
:root {
  /* Dark Theme Base */
  --background: #0a0a0a;           /* Deep black background */
  --foreground: #ffffff;           /* Pure white text */
  
  /* Semantic Colors */
  --card: #111111;                 /* Card backgrounds */
  --card-foreground: #ffffff;      /* Card text */
  --border: #1f1f1f;               /* Subtle borders */
  --input: #1f1f1f;               /* Input backgrounds */
  
  /* Accent Gradients */
  --primary: linear-gradient(135deg, #00d4aa 0%, #00b4d8 100%);  /* Aqua gradient */
  --secondary: linear-gradient(135deg, #9c27b0 0%, #673ab7 100%); /* Purple gradient */
  --accent: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%);    /* Orange gradient */
  
  /* Status Colors */
  --success: #10b981;              /* Green for success states */
  --warning: #f59e0b;              /* Amber for warnings */
  --error: #ef4444;                /* Red for errors */
  --info: #3b82f6;                 /* Blue for info */
}
```

#### Typography System

```css
/* Font Stack */
font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

/* Semantic Text Sizes */
.text-xs    { font-size: 0.75rem; line-height: 1rem; }     /* 12px - Small labels */
.text-sm    { font-size: 0.875rem; line-height: 1.25rem; } /* 14px - Body text */
.text-base  { font-size: 1rem; line-height: 1.5rem; }      /* 16px - Default */
.text-lg    { font-size: 1.125rem; line-height: 1.75rem; } /* 18px - Headings */
.text-xl    { font-size: 1.25rem; line-height: 1.75rem; }  /* 20px - Large headings */

/* Text Colors */
.text-ink      { color: #ffffff; }     /* Primary text */
.text-sub      { color: #a1a1aa; }     /* Secondary text */
.text-muted    { color: #71717a; }     /* Muted text */
```

#### Component Architecture

##### 1. **Card Component** (`ui/components/ui/Card.tsx`)
```tsx
// Glass morphism effect with subtle borders
className="bg-bg border border-white/5 rounded-xl p-6 backdrop-blur-sm"

// Features:
- Semi-transparent background with backdrop blur
- Subtle white borders (5% opacity)
- Consistent padding and rounded corners
- Hover effects with smooth transitions
```

##### 2. **Button Component** (`ui/components/ui/Button.tsx`)
```tsx
// Primary Button
className="bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-600 hover:to-cyan-600 text-white font-medium px-6 py-3 rounded-lg transition-all duration-200 transform hover:scale-105"

// Ghost Button  
className="border border-white/20 hover:border-white/40 text-white hover:bg-white/5 px-6 py-3 rounded-lg transition-all duration-200"

// Features:
- Gradient backgrounds with hover state changes
- Scale transform on hover (105%)
- Smooth transitions (200ms)
- Consistent padding and typography
```

##### 3. **Input & Select Components**
```tsx
// Input styling
className="bg-input border border-white/10 rounded-lg px-4 py-3 text-white placeholder-gray-400 focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 transition-all"

// Features:
- Dark input backgrounds
- Subtle borders that brighten on focus
- Teal accent color for focus states
- Smooth transitions for all state changes
```

#### Layout System

##### 1. **Grid Layouts**
```css
/* Main content grid */
.grid.grid-cols-1.lg\:grid-cols-2.gap-4 {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}

@media (min-width: 1024px) {
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}

/* Card grid for results */
.grid.grid-cols-1.gap-3 {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.75rem;
}
```

##### 2. **Flexbox Utilities**
```css
/* Header layout */
.flex.items-center.justify-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* Button groups */
.flex.items-center.gap-2 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
```

#### Animation System (Framer Motion)

##### 1. **Page Transitions**
```tsx
import { motion } from 'framer-motion';

// Page enter animation
<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.3, ease: "easeOut" }}
>
```

##### 2. **Component Animations**
```tsx
// Hover animations
<motion.div
  whileHover={{ scale: 1.02 }}
  whileTap={{ scale: 0.98 }}
  transition={{ type: "spring", stiffness: 300 }}
>

// Stagger animations for lists
<motion.div
  initial="hidden"
  animate="visible"
  variants={{
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  }}
>
```

#### Special Effects

##### 1. **Liquid Background** (`ui/components/LiquidBackground.tsx`)
```tsx
// Animated gradient background
const gradient = `
  radial-gradient(circle at 20% 50%, rgba(0, 212, 170, 0.1) 0%, transparent 50%),
  radial-gradient(circle at 80% 20%, rgba(156, 39, 176, 0.1) 0%, transparent 50%),
  radial-gradient(circle at 40% 80%, rgba(255, 107, 53, 0.1) 0%, transparent 50%)
`;

// Features:
- Multiple animated gradient circles
- Low opacity (10%) for subtle effect
- Smooth position animations
- Performance optimized with CSS transforms
```

##### 2. **Loading States**
```tsx
// Skeleton loading
className="animate-pulse bg-gray-800 rounded-lg h-4 w-full"

// Spinner component
<motion.div
  animate={{ rotate: 360 }}
  transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
  className="w-6 h-6 border-2 border-teal-500 border-t-transparent rounded-full"
/>
```

#### Responsive Design

##### 1. **Breakpoint System**
```css
/* Tailwind's responsive prefixes */
sm: 640px   /* Small devices */
md: 768px   /* Medium devices */
lg: 1024px  /* Large devices */
xl: 1280px  /* Extra large devices */
2xl: 1536px /* 2X large devices */

/* Usage examples */
className="text-sm md:text-base lg:text-lg"  /* Responsive typography */
className="grid-cols-1 md:grid-cols-2 lg:grid-cols-3"  /* Responsive grids */
```

##### 2. **Mobile-First Approach**
```css
/* Base styles for mobile */
.component {
  padding: 1rem;
  font-size: 0.875rem;
}

/* Progressive enhancement for larger screens */
@media (min-width: 768px) {
  .component {
    padding: 1.5rem;
    font-size: 1rem;
  }
}

@media (min-width: 1024px) {
  .component {
    padding: 2rem;
    font-size: 1.125rem;
  }
}
```

#### Accessibility Features

##### 1. **Focus Management**
```css
/* Focus rings for keyboard navigation */
.focus\:ring-2:focus {
  outline: 2px solid transparent;
  outline-offset: 2px;
  box-shadow: 0 0 0 2px rgba(20, 184, 166, 0.5);
}

/* High contrast mode support */
@media (prefers-contrast: high) {
  .text-sub { color: #d1d5db; }  /* Higher contrast secondary text */
}
```

##### 2. **Semantic HTML**
```tsx
// Proper heading hierarchy
<h1>Main Title</h1>
<h2>Section Title</h2>
<h3>Subsection Title</h3>

// ARIA labels for interactive elements
<button aria-label="Toggle timeline visibility">
  <span aria-hidden="true">Show Details</span>
</button>
```

#### Performance Optimizations

##### 1. **CSS Optimization**
```css
/* Hardware acceleration for animations */
.animate-transform {
  transform: translateZ(0);
  will-change: transform;
}

/* Efficient selectors */
.component__element { /* BEM methodology */ }
.component:hover .component__element { /* Efficient hover states */ }
```

##### 2. **Bundle Optimization**
```javascript
// Dynamic imports for heavy components
const LiquidBackground = dynamic(() => import('./LiquidBackground'), {
  ssr: false
});

// Tree shaking for unused CSS
// Tailwind's purge configuration removes unused styles
```

### Responsive Layout
- **Mobile-first**: Works on all screen sizes
- **Grid System**: CSS Grid and Flexbox for complex layouts
- **Sticky Elements**: Header and control bar remain accessible

### Real-time Updates
- **Server-Sent Events**: Live progress tracking
- **Loading States**: Skeletons and spinners for better UX
- **Error Handling**: Graceful error display and recovery

## 🔍 Troubleshooting

### Common Issues

#### PDF Upload Fails
```bash
# Check PDF library availability
curl http://localhost:8000/debug/pdf

# Install missing libraries
.venv\Scripts\python.exe -m pip install PyMuPDF pypdf pdfplumber
```

#### API Key Issues
- Verify `.env` file location and format
- Check API key validity and quotas
- Review terminal logs for specific error messages

#### Resume Not Merging
- Ensure PDF upload completes successfully
- Check browser console for upload confirmation
- Verify resume token in RAG timeline messages

#### No Companies Found
- Verify Exa.ai API key and credits
- Check search location spelling
- Review role configuration in `data/seeds/roles.yaml`

### Debug Commands
```bash
# Test PDF libraries
.venv\Scripts\python.exe -c "import fitz, pypdf, pdfplumber; print('All PDF libs OK')"

# Test API connectivity
curl -H "Authorization: Bearer YOUR_EXA_KEY" https://api.exa.ai/search

# Check server health
curl http://localhost:8000/debug/pdf
```

## 📈 Performance Optimization

### Credit Management
- **RAG Agent**: Limited to 5 companies max, 3 per role search
- **Enhanced Research**: Optional (disabled by default), reduced intelligence types
- **Exa Search**: Optimized queries, reduced result counts

### API Efficiency
- **Batch Processing**: Parallel company analysis
- **Caching**: In-memory resume and RAG document storage
- **Connection Pooling**: Async HTTP clients with proper cleanup

### Frontend Optimization
- **Code Splitting**: Next.js automatic splitting
- **Image Optimization**: Next.js Image component
- **Lazy Loading**: Components load on demand

## 🔐 Security Considerations

- **API Keys**: Stored in environment variables, never in code
- **File Upload**: PDF validation and size limits
- **CORS**: Configured for development (localhost:3000)
- **Input Validation**: Pydantic models for API endpoints

## 🚧 Development Guidelines

### Code Style
- **Python**: Follow PEP 8, use type hints
- **TypeScript**: Strict mode enabled, consistent interfaces
- **CSS**: Tailwind utilities, semantic class names

### Testing Strategy
- **Backend**: Debug endpoints for API testing
- **Frontend**: Browser console for state debugging
- **Integration**: End-to-end workflow testing

### Git Workflow
- **Feature Branches**: Separate branches for new features
- **Commit Messages**: Descriptive, include component affected
- **Code Review**: Required for main branch changes

## 📚 Dependencies

### Backend Core
- `fastapi>=0.104.0` - Web framework
- `uvicorn>=0.24.0` - ASGI server
- `pydantic>=2.5.0` - Data validation
- `httpx>=0.25.0` - Async HTTP client
- `python-dotenv>=1.0.0` - Environment variables

### PDF Processing
- `PyMuPDF>=1.26.0` - Primary PDF parser
- `pypdf>=5.5.0` - Fallback PDF parser
- `pdfplumber>=0.11.0` - Alternative PDF parser

### Frontend Core
- `next>=13.5.0` - React framework
- `react>=18.2.0` - UI library
- `typescript>=5.2.0` - Type safety
- `tailwindcss>=3.4.0` - Styling framework
- `framer-motion>=10.16.0` - Animations

### UI Components
- `@radix-ui/react-select` - Accessible dropdown
- `@radix-ui/react-icons` - Icon library

## 📄 License

[Add your license information here]

## 🤝 Contributing

[Add contribution guidelines here]

## 📧 Contact

[Add contact information here]

---

**Last Updated**: January 2025
**Version**: 1.0.0
**Status**: Production Ready