# CSR Workflow Testing Plan

## 🎯 **TESTING OBJECTIVE**
Verify complete CSR workflow: **CallRail → Backend → UWC → Twilio → Database**

## 📋 **TESTING CHECKLIST**

### **1. Railway Deployment ✅**
- [x] Fix import-time errors (UWC client, Twilio client)
- [x] Verify app starts successfully
- [x] Check all services initialize properly

### **2. CallRail Integration Testing**
- [ ] **Pre-call Webhook**: Test inbound call detection
- [ ] **Call-complete Webhook**: Test call completion processing
- [ ] **Lead Auto-Creation**: Verify new leads are created
- [ ] **Missed Call SMS**: Test auto-SMS for missed calls
- [ ] **Data Flow**: Verify call data reaches database

### **3. UWC/Shunya Integration Testing**
- [ ] **ASR Service**: Test audio transcription
- [ ] **RAG Service**: Test document querying
- [ ] **Training Service**: Test personal clone training
- [ ] **API Connectivity**: Verify UWC endpoints are reachable

### **4. Twilio Integration Testing**
- [ ] **SMS Sending**: Test outbound SMS functionality
- [ ] **Call Initiation**: Test outbound call functionality
- [ ] **Webhook Processing**: Test incoming SMS/call status
- [ ] **Recording Callbacks**: Test call recording processing

### **5. Database Integration Testing**
- [ ] **Call Records**: Verify call data is stored correctly
- [ ] **Transcripts**: Verify transcription data is saved
- [ ] **Lead Management**: Verify lead creation and updates
- [ ] **Real-time Events**: Verify event emission works

## 🧪 **TESTING METHODS**

### **Manual Testing**
1. **CallRail Webhook Simulation**
   ```bash
   curl -X POST "https://your-railway-url.com/webhook/callrail/pre-call" \
        -H "Content-Type: application/json" \
        -d '{"callernum": "+1234567890", "trackingnum": "+1987654321", "answered": "false"}'
   ```

2. **UWC Service Testing**
   ```bash
   curl -X POST "https://your-railway-url.com/api/v1/rag/query" \
        -H "Authorization: Bearer YOUR_TOKEN" \
        -d '{"query": "test query", "context": "test context"}'
   ```

3. **Twilio SMS Testing**
   ```bash
   curl -X POST "https://your-railway-url.com/mobile/twilio-send-text" \
        -H "Content-Type: application/json" \
        -d '{"call_id": 123, "to": "+1234567890", "message": "Test message"}'
   ```

### **Automated Testing**
1. **Unit Tests**: Test individual components
2. **Integration Tests**: Test service interactions
3. **End-to-End Tests**: Test complete workflows

## 📊 **SUCCESS CRITERIA**

### **CallRail → Backend**
- ✅ Inbound call detected and logged
- ✅ Lead auto-creation works for new numbers
- ✅ Missed call SMS sent automatically
- ✅ Call data stored in database

### **Backend → UWC**
- ✅ ASR transcription works
- ✅ RAG queries return results
- ✅ Training jobs submit successfully
- ✅ Error handling works gracefully

### **Backend → Twilio**
- ✅ SMS sending works
- ✅ Call initiation works
- ✅ Webhook processing works
- ✅ Recording callbacks work

### **Database → Frontend**
- ✅ Call records visible in dashboard
- ✅ Real-time updates work
- ✅ Analytics data populates
- ✅ User permissions work correctly

## 🚨 **KNOWN ISSUES TO FIX**

1. **UWC Configuration**: Need to set up UWC_API_KEY and UWC_BASE_URL
2. **Twilio Credentials**: Need to configure TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN
3. **CallRail Setup**: Need to configure CALLRAIL_API_KEY and webhook URLs
4. **Database Migrations**: May need to run migrations for new features

## 📈 **NEXT STEPS**

1. **Configure External Services** (UWC, Twilio, CallRail)
2. **Test Each Integration** individually
3. **Test End-to-End Workflow** 
4. **Monitor Data Flow** and performance
5. **Fix Any Issues** found during testing
