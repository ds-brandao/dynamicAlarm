#!/bin/bash

# Get tomorrow's date
tomorrow_date=$(date -v+1d "+%m/%d/%Y")

# Convert the input time to a format that AppleScript can understand
time_formatted="$tomorrow_date $1"

# Create an AppleScript command to create a new event in the Calendar app
osascript <<EOF
tell application "Calendar" to activate
tell application "Calendar"
    tell calendar "Alarm"
        make new event at end with properties {description:"Alarm", start date:date "$time_formatted", end date:date "$time_formatted", allday event:false}
    end tell
end tell
EOF