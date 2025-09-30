Logic of work

┌─────────────────────────────────────────────────────────┐
│                 BLOOD PRESSURE DIARY BOT                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  MAIN MENU:                                             │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │      Add        │  │     Show        │              │
│  └─────────────────┘  └─────────────────┘              │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │    Export       │  │    Delete       │              │
│  └─────────────────┘  └─────────────────┘              │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │    Status       │  │   Settings      │              │
│  └─────────────────┘  └─────────────────┘              │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                     ADD FLOW:                           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  Enter BP   │ -> │ Enter Pulse │ -> │ Add Comment │  │
│  │  120/80     │    │     72      │    │   "Morning" │  │
│  └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                    DELETE FLOW:                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ 🗑️ Select entry to delete:                          ││
│  │                                                     ││
│  │ 1. 2024-01-15 08:30                                ││
│  │    BP: 120/80 | Pulse: 72                          ││
│  │    Note: Morning measurement                       ││
│  │                                                     ││
│  │ 2. 2024-01-14 20:15                                ││
│  │    BP: 118/78 | Pulse: 68                          ││
│  │    Note: Evening measurement                       ││
│  │                                                     ││
│  │ Buttons: [1] [2] [3] [4] [5] ... [10] [Cancel]     ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
├─────────────────────────────────────────────────────────┤
│                    SETTINGS FLOW:                       │
│  ┌─────────────────┐    ┌─────────────────────────────┐ │
│  │  Set Timezone   │ -> │ 🌍 Choose timezone:        │ │
│  └─────────────────┘    │ [New York] [London]         │ │
│                         │ [Berlin]   [Tokyo]          │ │
│  ┌─────────────────┐    │ [Moscow]   [Sydney]         │ │
│  │ Set Reminders   │ -> │ [Los Angeles] [Other]       │ │
│  └─────────────────┘    └─────────────────────────────┘ │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ ⏰ Set two daily reminders:                         ││
│  │ [07:00 19:00] [08:00 20:00] [09:00 21:00]          ││
│  │ [Custom Times] [Cancel]                             ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
├─────────────────────────────────────────────────────────┤
│                    EXPORT FLOW:                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ 📤 Choose format to export:                         ││
│  │ [CSV] [XLSX] [PDF] [Cancel]                         ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
└─────────────────────────────────────────────────────────┘

1. MAIN MENU INTERFACE:

┌─────────────────────────────────────────┐
│           BLOOD PRESSURE BOT            │
│                                         │
│   [Add]       [Show]       [Export]     │
│   [Delete]    [Status]     [Settings]   │
│                                         │
│  👋 Track your health measurements!     │
└─────────────────────────────────────────┘

2. ADD ENTRY FLOW:

STEP 1:          STEP 2:          STEP 3:
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ Enter BP:   │  │ Enter Pulse:│  │ Add Comment:│
│  120/80     │  │     72      │  │  "Morning"  │
└─────────────┘  └─────────────┘  └─────────────┘

3. DELETE INTERFACE:

┌─────────────────────────────────────────┐
│ 🗑️ SELECT ENTRY TO DELETE:              │
│                                         │
│ 1. Jan 15, 08:30 - BP: 120/80 P:72     │
│    Note: Morning measurement            │
│                                         │
│ 2. Jan 14, 20:15 - BP: 118/78 P:68     │
│    Note: Evening measurement            │
│                                         │
│ [1] [2] [3] [4] [5] [6] [7] [8] [9] [10]│
│              [Cancel]                   │
└─────────────────────────────────────────┘

4. SETTINGS INTERFACE:

TIMEZONE SETTINGS:         REMINDER SETTINGS:
┌─────────────────────┐    ┌─────────────────────┐
│ 🌍 Choose timezone: │    │ ⏰ Set reminders:   │
│                     │    │                     │
│ [New York] [London] │    │ [07:00 19:00]       │
│ [Berlin]   [Tokyo]  │    │ [08:00 20:00]       │
│ [Moscow]   [Sydney] │    │ [09:00 21:00]       │
│ [LA]       [Other]  │    │ [Custom] [Cancel]   │
│ [Cancel]            │    │                     │
└─────────────────────┘    └─────────────────────┘

5. STATUS DISPLAY:

┌─────────────────────────────────────────┐
│ 📊 YOUR STATUS:                         │
│                                         │
│ 🌍 Timezone: Europe/Berlin              │
│ ⏰ Reminders: 08:00 and 20:00           │
│ 📈 Total entries: 47                    │
│ 📅 Today's entries: 2                   │
│                                         │
│ Last measurement: 125/82 P:75           │
└─────────────────────────────────────────┘

6. DATA FLOW ARCHITECTURE:

USER INPUT
    ↓
TELEGRAM BOT
    ↓
DATABASE (SQLite)
    ├── bp_diary table
    │   ├── chat_id
    │   ├── datetime  
    │   ├── bp (120/80)
    │   ├── pulse (72)
    │   └── comment
    │
    └── user_settings table
        ├── user_id
        ├── timezone
        └── reminders (JSON)
            ↓
EXPORT OPTIONS
    ├── CSV 📊
    ├── Excel 📈
    └── PDF 📄

7. REMINDER SYSTEM:

⏰ DAILY REMINDER FLOW:
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Check Time  │ →  │ User TZ     │ →  │ Send Msg    │
│ Every 30s   │    │ Conversion  │    │ "Measure BP!"│
└─────────────┘    └─────────────┘    └─────────────┘
        │                 │                 │
    UTC Time        User's Local        Telegram
                    Timezone           Notification

