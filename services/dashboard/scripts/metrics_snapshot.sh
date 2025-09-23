#!/bin/bash

# OttoAI Backend - Metrics Snapshot Helper
# Fetches and summarizes key metrics from the /metrics endpoint

set -e

# Configuration
BASE_URL="${1:-https://tv-mvp-test.fly.dev}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-summary}"  # summary|full|json

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Fetch metrics from endpoint
fetch_metrics() {
    local url="$BASE_URL/metrics"
    
    log_info "Fetching metrics from: $url"
    
    if ! curl -s "$url" > /tmp/metrics.txt 2>/dev/null; then
        log_error "Failed to fetch metrics from $url"
        exit 1
    fi
    
    if [ ! -s /tmp/metrics.txt ]; then
        log_error "Empty metrics response"
        exit 1
    fi
    
    log_info "Metrics fetched successfully"
}

# Parse metric value
get_metric_value() {
    local metric_name="$1"
    local labels="$2"
    
    if [ -n "$labels" ]; then
        grep "^${metric_name}{${labels}}" /tmp/metrics.txt | tail -n 1 | awk '{print $2}'
    else
        grep "^${metric_name}" /tmp/metrics.txt | tail -n 1 | awk '{print $2}'
    fi
}

# Calculate percentile from histogram
calculate_percentile() {
    local metric_name="$1"
    local percentile="$2"  # e.g., 0.95 for p95
    
    # Extract histogram buckets
    grep "^${metric_name}_bucket" /tmp/metrics.txt | while read -r line; do
        echo "$line"
    done | sort -t'=' -k2 -n > /tmp/histogram.txt
    
    # Simple percentile calculation (approximate)
    local total_count=$(grep "^${metric_name}_count" /tmp/metrics.txt | awk '{print $2}')
    if [ -z "$total_count" ] || [ "$total_count" = "0" ]; then
        echo "0"
        return
    fi
    
    local target_count=$(echo "$total_count * $percentile" | bc -l 2>/dev/null || echo "$total_count")
    
    # Find bucket that contains the percentile
    local cumulative=0
    while read -r line; do
        local bucket_value=$(echo "$line" | grep -o 'le="[^"]*"' | cut -d'"' -f2)
        local bucket_count=$(echo "$line" | awk '{print $2}')
        
        cumulative=$(echo "$cumulative + $bucket_count" | bc -l 2>/dev/null || echo "$cumulative")
        
        if [ "$(echo "$cumulative >= $target_count" | bc -l 2>/dev/null || echo "1")" = "1" ]; then
            echo "$bucket_value"
            return
        fi
    done < /tmp/histogram.txt
    
    echo "unknown"
}

# Generate summary report
generate_summary() {
    echo -e "\n${BOLD}${BLUE}📊 OTTOAI BACKEND METRICS SNAPSHOT${NC}"
    echo -e "${BLUE}Timestamp: $(date)${NC}"
    echo -e "${BLUE}Source: $BASE_URL/metrics${NC}"
    
    echo -e "\n${BOLD}🔗 WebSocket Connections${NC}"
    local ws_connections=$(get_metric_value "ws_connections")
    local ws_messages_sent=$(get_metric_value "ws_messages_sent_total")
    local ws_messages_dropped=$(get_metric_value "ws_messages_dropped_total")
    
    echo -e "  Active Connections: ${ws_connections:-0}"
    echo -e "  Messages Sent: ${ws_messages_sent:-0}"
    echo -e "  Messages Dropped: ${ws_messages_dropped:-0}"
    
    if [ "${ws_messages_dropped:-0}" -gt 0 ]; then
        echo -e "  ${YELLOW}⚠️  Messages are being dropped${NC}"
    else
        echo -e "  ${GREEN}✅ No messages dropped${NC}"
    fi
    
    echo -e "\n${BOLD}🌐 HTTP Requests${NC}"
    local http_requests=$(get_metric_value "http_requests_total")
    local p95_latency=$(calculate_percentile "http_request_duration_ms" "0.95")
    
    echo -e "  Total Requests: ${http_requests:-0}"
    echo -e "  P95 Latency: ${p95_latency:-unknown}ms"
    
    if [ -n "$p95_latency" ] && [ "$p95_latency" != "unknown" ]; then
        if [ "$(echo "$p95_latency < 250" | bc -l 2>/dev/null || echo "1")" = "1" ]; then
            echo -e "  ${GREEN}✅ Latency healthy (<250ms)${NC}"
        elif [ "$(echo "$p95_latency < 1000" | bc -l 2>/dev/null || echo "1")" = "1" ]; then
            echo -e "  ${YELLOW}⚠️  Latency elevated (${p95_latency}ms)${NC}"
        else
            echo -e "  ${RED}❌ Latency high (${p95_latency}ms)${NC}"
        fi
    fi
    
    echo -e "\n${BOLD}⚙️  Worker Tasks${NC}"
    local worker_tasks=$(get_metric_value "worker_task_total")
    local worker_success=$(get_metric_value "worker_task_total" 'status="success"')
    local worker_failure=$(get_metric_value "worker_task_total" 'status="failure"')
    
    echo -e "  Total Tasks: ${worker_tasks:-0}"
    echo -e "  Successful: ${worker_success:-0}"
    echo -e "  Failed: ${worker_failure:-0}"
    
    if [ "${worker_failure:-0}" -gt 0 ]; then
        echo -e "  ${YELLOW}⚠️  Some worker tasks are failing${NC}"
    else
        echo -e "  ${GREEN}✅ All worker tasks successful${NC}"
    fi
    
    echo -e "\n${BOLD}🔄 Webhook Processing${NC}"
    local webhook_processed=$(get_metric_value "webhook_processed_total")
    local webhook_duplicates=$(get_metric_value "webhook_duplicates_total")
    local webhook_failures=$(get_metric_value "webhook_failures_total")
    
    echo -e "  Processed: ${webhook_processed:-0}"
    echo -e "  Duplicates: ${webhook_duplicates:-0}"
    echo -e "  Failures: ${webhook_failures:-0}"
    
    if [ "${webhook_failures:-0}" -gt 0 ]; then
        echo -e "  ${YELLOW}⚠️  Some webhooks are failing${NC}"
    else
        echo -e "  ${GREEN}✅ All webhooks processing successfully${NC}"
    fi
    
    echo -e "\n${BOLD}💾 Cache Performance${NC}"
    local cache_hits=$(get_metric_value "cache_hits_total")
    local cache_misses=$(get_metric_value "cache_misses_total")
    
    echo -e "  Cache Hits: ${cache_hits:-0}"
    echo -e "  Cache Misses: ${cache_misses:-0}"
    
    if [ "${cache_hits:-0}" -gt 0 ] && [ "${cache_misses:-0}" -gt 0 ]; then
        local hit_rate=$(echo "scale=2; $cache_hits * 100 / ($cache_hits + $cache_misses)" | bc -l 2>/dev/null || echo "unknown")
        echo -e "  Hit Rate: ${hit_rate}%"
        
        if [ "$(echo "$hit_rate > 80" | bc -l 2>/dev/null || echo "0")" = "1" ]; then
            echo -e "  ${GREEN}✅ Cache performance good${NC}"
        else
            echo -e "  ${YELLOW}⚠️  Cache hit rate could be improved${NC}"
        fi
    fi
    
    echo -e "\n${BOLD}📈 Overall Health${NC}"
    
    # Determine overall health status
    local health_issues=0
    
    if [ "${ws_messages_dropped:-0}" -gt 0 ]; then
        ((health_issues++))
    fi
    
    if [ -n "$p95_latency" ] && [ "$p95_latency" != "unknown" ] && [ "$(echo "$p95_latency > 1000" | bc -l 2>/dev/null || echo "0")" = "1" ]; then
        ((health_issues++))
    fi
    
    if [ "${webhook_failures:-0}" -gt 0 ]; then
        ((health_issues++))
    fi
    
    if [ $health_issues -eq 0 ]; then
        echo -e "  ${GREEN}${BOLD}🎉 ALL SYSTEMS HEALTHY 🎉${NC}"
    elif [ $health_issues -le 2 ]; then
        echo -e "  ${YELLOW}${BOLD}⚠️  MINOR ISSUES DETECTED ⚠️${NC}"
    else
        echo -e "  ${RED}${BOLD}❌ MULTIPLE ISSUES DETECTED ❌${NC}"
    fi
    
    echo -e "\n${BLUE}Snapshot completed at: $(date)${NC}"
}

# Generate JSON output
generate_json() {
    local ws_connections=$(get_metric_value "ws_connections")
    local ws_messages_sent=$(get_metric_value "ws_messages_sent_total")
    local ws_messages_dropped=$(get_metric_value "ws_messages_dropped_total")
    local http_requests=$(get_metric_value "http_requests_total")
    local p95_latency=$(calculate_percentile "http_request_duration_ms" "0.95")
    local worker_tasks=$(get_metric_value "worker_task_total")
    
    cat << EOF
{
  "timestamp": "$(date -Iseconds)",
  "source": "$BASE_URL/metrics",
  "websocket": {
    "connections": ${ws_connections:-0},
    "messages_sent": ${ws_messages_sent:-0},
    "messages_dropped": ${ws_messages_dropped:-0}
  },
  "http": {
    "total_requests": ${http_requests:-0},
    "p95_latency_ms": ${p95_latency:-null}
  },
  "workers": {
    "total_tasks": ${worker_tasks:-0}
  }
}
EOF
}

# Check command line arguments
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "OttoAI Backend Metrics Snapshot"
    echo ""
    echo "Usage: $0 [BASE_URL] [--format=summary|full|json]"
    echo ""
    echo "Arguments:"
    echo "  BASE_URL      Backend URL (default: https://tv-mvp-test.fly.dev)"
    echo ""
    echo "Options:"
    echo "  --format      Output format (summary|full|json)"
    echo "  --help, -h    Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  OUTPUT_FORMAT Format for output (summary|full|json)"
    echo ""
    echo "Examples:"
    echo "  $0"
    echo "  $0 https://staging.ottoai.com"
    echo "  $0 --format=json"
    echo "  OUTPUT_FORMAT=json $0"
    exit 0
fi

# Parse format option
if [[ "$2" == --format=* ]]; then
    OUTPUT_FORMAT="${2#--format=}"
fi

# Fetch metrics
fetch_metrics

# Generate output based on format
case "$OUTPUT_FORMAT" in
    "json")
        generate_json
        ;;
    "full")
        cat /tmp/metrics.txt
        ;;
    "summary"|*)
        main
        ;;
esac

# Cleanup
rm -f /tmp/metrics.txt /tmp/histogram.txt
