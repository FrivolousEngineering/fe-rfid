#include <EEPROM.h>
#include <MFRC522.h>
#include <SPI.h>

// NAno pinout??
#define RST_PIN 9
#define SS_PIN 10

#define MAX_CMD_LEN 128

// ESP PINOUT
// #define SS_PIN 5
// #define RST_PIN 0

MFRC522 mfrc522(SS_PIN, RST_PIN); // Instance of the class
MFRC522::MIFARE_Key key;
MFRC522::StatusCode status;

int errorCount = 0;
const int errorThreshold = 3;
String detected_tag = "";
bool printMemory = false;
bool printCardType = false;
String data_to_write = "";
byte blockData[16] = {};
byte buffer[18]; // To hold the read data
int blocks_to_read[10] = { 0 };
bool ignore_card_remove_event = false;

struct MemoryMap {
    byte sample_type;
    byte primary_action;
    byte primary_target;
    byte secondary_action;
    byte secondary_target;
    byte depleted;
    byte purity;
};

// Define the memory mapping on the chips. Note that the numbers mean something quite different for both of em.
// Mifare use adresses that are 16 bytes, ntag uses adresses that are 4 bytes.
// MemoryMap mifareMapping = {4, 5, 6, 8, 9, 10, 12};
// MemoryMap ntagMapping = {6, 9, 12, 15, 18, 21, 24};

MemoryMap activeMapping = { 6, 10, 14, 18, 22, 26, 30 };

char* sample_type_to_write = "";
char* primary_action_to_write = "";
char* primary_target_to_write = "";
char* secondary_action_to_write = "";
char* secondary_target_to_write = "";
char* depleted_to_write = "";
char* purity_to_write = "";

const char validPurities[][12] PROGMEM = {
    "POLLUTED", "TARNISHED", "DIRTY", "BLEMISHED",
    "IMPURE", "UNBLEMISHED", "LUCID", "STAINLESS",
    "PRISTINE", "IMMACULATE", "PERFECT"
};

const char validActions[][16] PROGMEM = {
    "EXPANDING", "CONTRACTING", "CONDUCTING", "INSULATING",
    "DETERIORATING", "CREATING", "DESTROYING", "INCREASING",
    "DECREASING", "ABSORBING", "RELEASING", "SOLIDIFYING",
    "LIGHTENING", "ENCUMBERING", "FORTIFYING", "HEATING", "COOLING"
};

// Store valid targets in flash memory (PROGMEM)
const char validTargets[][8] PROGMEM = {
    "FLESH", "MIND", "GAS", "SOLID", "LIQUID",
    "ENERGY", "LIGHT", "SOUND", "KRYSTAL", "PLANT"
};

void setup()
{
    Serial.begin(115200);
    SPI.begin(); // Init SPI bus
    mfrc522.PCD_Init(); // Init MFRC522

    Serial.print("Reader has booted. Chip state: ");
    Serial.println(mfrc522.PCD_PerformSelfTest()); // Prints 1 if the reader was correctly identified. If it's wired/soldered incorrectly or some kind of fucked counterfeit it will print 0
    // Initialize default key
    for (byte i = 0; i < 6; i++) {
        key.keyByte[i] = 0xFF;
    }
}

String toHexString(byte* buffer, byte bufferSize)
{
    String result = "";
    for (byte i = 0; i < bufferSize; i++) {
        result += buffer[i] < 0x10 ? "0" : "";
        result += String(buffer[i], HEX);
    }
    return result;
}

void printHex(byte* buffer, byte bufferSize)
{
    for (byte i = 0; i < bufferSize; i++) {
        Serial.print(buffer[i] < 0x10 ? " 0" : " ");
        Serial.print(buffer[i], HEX);
    }
    Serial.println();
}

/**
 * Read string from a 4 byte ntag page
 */
String readPage(byte page)
{
    byte buffer[18];
    byte size = sizeof(buffer);
    MFRC522::StatusCode status = mfrc522.MIFARE_Read(page, buffer, &size);
    if (status != MFRC522::STATUS_OK) {
        Serial.print("Failed to read page ");
        Serial.println(page);
        return "";
    }
    String data = "";
    for (byte i = 0; i < 4; i++) {
        data += buffer[i] != 0 ? (char)buffer[i] : ' ';
    }
    return data;
}

void readCardMemoryNTAG()
{
    for (byte page = 0; page < 45; page++) { // Adjust based on NTAG type (213=45, 215=135)
        String data = readPage(page);
        Serial.print("Page ");
        Serial.print(page);
        Serial.print(": ");
        Serial.println(data);
    }
}

String padToBytesLength(String data, int length = 16)
{
    while (data.length() < length) {
        data += ' ';
    }
    return data;
}

/**
 * Write a string that is larger than 4 bytes to a card.
 * Note that pages are 4 bytes. So when writing 5 bytes, we will use
 * 2 pages (aka; 8 bytes of memory). For convenience sake we don't do
 * any fragmentation or packing.
 * We also don't have any protection to check if we are going over memory or
 * if we are writing in memory that you shouldn't be writing to as of yet.
 * This means it's possible to brick tags if you are not carefull.
 */
bool writeLargeStringToNTAG(byte startPage, String data)
{
    data = padToBytesLength(data, 16); // We pad them to 12 to ensure any old data is overridden.
    int length = data.length();
    int pageOffset = 0;

    // Iterate through the string in chunks of 4 bytes
    for (int i = 0; i < length; i += 4) {
        byte buffer[4] = { 0x00, 0x00, 0x00, 0x00 }; // Initialize 4-byte buffer

        // Copy 4 bytes or less from the string into the buffer
        for (int j = 0; j < 4; j++) {
            if ((i + j) < length) {
                buffer[j] = data[i + j];
            } else {
                buffer[j] = 0x00; // Padding if the string is shorter than 4 bytes
            }
        }

        // Write to the current page
        if (!writeDataToPageNTAG(startPage + pageOffset, buffer)) {
            Serial.println("Failed to write");
            return false;
        }

        pageOffset++;
    }
    return true;
}

bool writeDataToPageNTAG(byte page, byte* data)
{
    MFRC522::StatusCode status;
    status = mfrc522.MIFARE_Ultralight_Write(page, data, 4);
    if (status != MFRC522::STATUS_OK) {
        Serial.print("Write failed ");
        Serial.print(page);
        Serial.print(": ");
        Serial.println(mfrc522.GetStatusCodeName(status));
        return false;
    }
    return true;
}

void readCardMemoryMifare()
{
    // Mifare style reading.
    byte buffer[18];
    byte size = sizeof(buffer);
    MFRC522::StatusCode status;

    for (byte block = 0; block < 64; block++) {
        // Authenticate before reading
        status = mfrc522.PCD_Authenticate(MFRC522::PICC_CMD_MF_AUTH_KEY_A, block, &key, &(mfrc522.uid));
        if (status != MFRC522::STATUS_OK) {
            Serial.print("Failed to auth block ");
            Serial.println(block);
            continue;
        }

        status = mfrc522.MIFARE_Read(block, buffer, &size);
        if (status == MFRC522::STATUS_OK) {
            Serial.print("Block ");
            Serial.print(block);
            Serial.print(": ");
            printHex(buffer, 16);
        } else {
            Serial.print("Failed to read block ");
            Serial.println(block);
        }
    }
    ignore_card_remove_event = true;
}

bool isValidDepleted(const String& depleted)
{
    return depleted == "DEPLETED" || depleted == "ACTIVE";
}

void trim(char* str)
{
    int len = strlen(str);
    while (len > 0 && (str[len - 1] == '\r' || str[len - 1] == '\n' || str[len - 1] == ' ')) {
        str[--len] = '\0';
    }
}

void processCommand(String command)
{

    char cmdBuffer[MAX_CMD_LEN];
    memset(cmdBuffer, 0, sizeof(cmdBuffer)); // Clear buffer to prevent leftover data

    // Ensure we don't overflow
    int len = command.length();
    if (len >= MAX_CMD_LEN) {
        Serial.println("Command too long");
        return;
    }

    command.toCharArray(cmdBuffer, MAX_CMD_LEN);
    cmdBuffer[sizeof(cmdBuffer) - 1] = '\0';

    trim(cmdBuffer); // Trim newlines and trailing spaces

    char* keyword = strtok(cmdBuffer, " ");
    char* argument = strtok(NULL, "");

    if (keyword == NULL)
        return;
    strupr(keyword); // Convert keyword to uppercase

    if (argument != NULL && strcmp(keyword, "WRITE") != 0) {
        strupr(argument);
    }

    if (strcmp(keyword, "WRITESAMPLE") == 0 && argument != NULL) {
        handleWriteSample(argument);
    } else if (strcmp(keyword, "READ") == 0) {
        handleReadCommand(argument);
    } else if (strcmp(keyword, "NAME") == 0) {
        handleNameCommand(argument);
    } else if (strcmp(keyword, "DEPLETESAMPLE") == 0){ // Mark the sample as depleted
        depleted_to_write = "DEPLETED";
        Serial.println("Marked sample as depleted");
    } else if (strcmp(keyword, "ACTIVATESAMPLE") == 0) {
        depleted_to_write = "ACTIVE";
        Serial.println("Marked sample as active");
    } else {
        Serial.print("Unknown command: ");
        Serial.println(keyword);
    }
}

void handleWriteSample(char* args)
{
    char* sample_type = strtok(args, " ");
    char* primary_action = strtok(NULL, " ");
    char* primary_target = strtok(NULL, " ");
    char* secondary_action = strtok(NULL, " ");
    char* secondary_target = strtok(NULL, " ");
    char* purity = strtok(NULL, " ");
    char* depleted = strtok(NULL, " ");

    if (!sample_type || !primary_action || !primary_target) {
        Serial.println("Invalid WRITESAMPLE format.");
        return;
    }

    if (strcmp(sample_type, "RAW") == 0) {
        if (!secondary_action || !secondary_target) {
            Serial.println("Secondary action or target missing for RAW sample.");
            return;
        }
        purity = "!";
    } else if (strcmp(sample_type, "REFINED") == 0) {
        if (!secondary_action || !secondary_target) {
            Serial.println("Secondary action or target missing for REFINED sample.");
            return;
        }
        if (!purity) {
            Serial.println("Purity missing for REFINED sample.");
            return;
        }
    } else if (strcmp(sample_type, "BLOOD") == 0) {
        purity = secondary_action;
        secondary_action = NULL;
        if (!purity) {
            Serial.println("Purity missing for BLOOD sample.");
            return;
        }
    }

    if (!depleted) {
        depleted = "ACTIVE"; // Default value
    }

    // Prepare the data to be written (this won't always work if we do it now as the card flips between being able to be read and not).
    // So we store them for the next loop when the reader is working correctly
    sample_type_to_write = sample_type;
    primary_target_to_write = primary_target;
    primary_action_to_write = primary_action;
    secondary_target_to_write = secondary_target;
    secondary_action_to_write = secondary_action;
    depleted_to_write = depleted;
    purity_to_write = purity;

    Serial.println("Write complete!");
}

void handleReadCommand(char* argument)
{
    memset(blocks_to_read, 0, sizeof(blocks_to_read));

    if (strcmp(argument, "ALL") == 0) {
        int index = 0;
        blocks_to_read[index++] = activeMapping.sample_type;
        blocks_to_read[index++] = activeMapping.primary_action;
        blocks_to_read[index++] = activeMapping.primary_target;
        blocks_to_read[index++] = activeMapping.secondary_action;
        blocks_to_read[index++] = activeMapping.secondary_target;
        blocks_to_read[index++] = activeMapping.depleted;
        blocks_to_read[index++] = activeMapping.purity;
    } else {
        int blockNum = atoi(argument);
        blocks_to_read[0] = blockNum;
    }
}

void handleNameCommand(char* argument)
{
    if (argument != NULL) {
        writeStringToEEPROM(0, argument);
        Serial.print("Setting name: ");
        Serial.println(argument);
    } else {
        char nameBuffer[32];
        readStringFromEEPROM(0, nameBuffer, sizeof(nameBuffer));
        Serial.print("Name: ");
        Serial.println(nameBuffer);
    }
}

String readLargeStringFromNTAG(byte startPage, int maxPages = 4)
{
    String result = "";

    for (byte i = 0; i < maxPages; i++) {
        result += readPage(startPage + i);
    }

    return trimTrailingSpaces(result);
}

void readBlocksToBuffer(char* buffer, size_t bufferSize)
{
    buffer[0] = '\0'; // Start with an empty buffer
    bool firstBlock = true;

    for (int i = 0; i < sizeof(blocks_to_read) / sizeof(blocks_to_read[0]); i++) {
        if (blocks_to_read[i] == 0)
            break;
        int current_block = blocks_to_read[i];

        // Read block into a temporary buffer
        char tempBuffer[48]; // Adjust based on typical block size
        memset(tempBuffer, 0, sizeof(tempBuffer));
        String result = readLargeStringFromNTAG(current_block); // Reading block as String

        // Copy the result into tempBuffer
        result.toCharArray(tempBuffer, sizeof(tempBuffer));

        // Concatenate to the main buffer
        if (!firstBlock) {
            strncat(buffer, " ", bufferSize - strlen(buffer) - 1); // Add space separator
        }

        strncat(buffer, tempBuffer, bufferSize - strlen(buffer) - 1); // Append block data

        firstBlock = false;
    }
}

void loop()
{
    if (Serial.available() > 0) {
        String command = Serial.readStringUntil('\n');
        processCommand(command);
    }

    if (mfrc522.PICC_IsNewCardPresent() && mfrc522.PICC_ReadCardSerial()) {
        if (detected_tag == "") {
            // A card was detected and we didn't have one already.
            detected_tag = toHexString(mfrc522.uid.uidByte, mfrc522.uid.size);
            if (!ignore_card_remove_event) {
                // We're not ignoring the "new card" event.
                Serial.print("Tag found: ");
                Serial.print(detected_tag);
                Serial.print(" ");
                // Fake a read all properties command so that we can get print it
                handleReadCommand("ALL");
                char resultBuffer[256];
                readBlocksToBuffer(resultBuffer, sizeof(resultBuffer));
                // If there is nothing in memory we will get a bunch of spaces.
                // Trim them so we can check if it's empty or not.
                trim(resultBuffer);
                if (strlen(resultBuffer) > 0) {
                    Serial.println(resultBuffer);
                    memset(blocks_to_read, 0, sizeof(blocks_to_read)); // Reset blocks_to_read after reading
                } else {
                    Serial.println("EMPTY");
                }
            } else {
                // If we are ignoring an event, we should start listening after ignoring it once.
                ignore_card_remove_event = false;
            }
        } else {
            // So, we do this indirectly, as the card reader seems to flip between being able to do something and not being able to do something.
            // Since we *know* that we are in a situation where it can do something, it's also the moment to write it. If we don't, we get random timeout issues
            // on the writing. We couldn't just use a normal retry, as it would try the same thing without allowing the states (or whatever the fuck is causing this)
            // to change. So future me (or idk, whoever reads this), learn from my folley. That retry stuff for the newCard present is there for a reason and it also affects the writing stuff.
            if (data_to_write != "") {
                writeLargeStringToNTAG(activeMapping.sample_type, data_to_write);
            }

            if (sample_type_to_write != "") {
                writeLargeStringToNTAG(activeMapping.sample_type, sample_type_to_write);
                sample_type_to_write = "";
            }
            if (primary_action_to_write != "") {
                writeLargeStringToNTAG(activeMapping.primary_action, primary_action_to_write);
                primary_action_to_write = "";
            }
            if (primary_target_to_write != "") {
                writeLargeStringToNTAG(activeMapping.primary_target, primary_target_to_write);
                primary_target_to_write = "";
            }

            if (secondary_action_to_write != "") {
                writeLargeStringToNTAG(activeMapping.secondary_action, secondary_action_to_write);
                secondary_action_to_write = "";
            }
            if (secondary_target_to_write != "") {
                writeLargeStringToNTAG(activeMapping.secondary_target, secondary_target_to_write);
                secondary_target_to_write = "";
            }

            if (depleted_to_write != "") {
                writeLargeStringToNTAG(activeMapping.depleted, depleted_to_write);
                depleted_to_write = "";
            }

            if (purity_to_write != "") {
                if (purity_to_write == "!") { // Special case, since we use empty strings as a way to check if we should do something, we use "!" as indication that stuff needs to be deleted
                    writeLargeStringToNTAG(activeMapping.purity, "");
                } else {
                    writeLargeStringToNTAG(activeMapping.purity, purity_to_write);
                }
                purity_to_write = "";
            }
            char resultBuffer[256];

            readBlocksToBuffer(resultBuffer, sizeof(resultBuffer));
            trim(resultBuffer);
            if (strlen(resultBuffer) > 0) {
                Serial.print("Traits: ");
                Serial.println(resultBuffer);
                memset(blocks_to_read, 0, sizeof(blocks_to_read)); // Reset blocks_to_read after reading
            }
        }
        errorCount = 0;
    } else {
        if (detected_tag != "") {
            errorCount++;
            if (errorCount > errorThreshold) {
                if (!ignore_card_remove_event) {
                    Serial.print("Tag lost: ");
                    Serial.println(detected_tag);
                }
                detected_tag = "";
                errorCount = 0;
                mfrc522.PICC_HaltA();
                mfrc522.PCD_StopCrypto1();
            }
        }
    }
}

String trimTrailingSpaces(String data)
{
    int i = data.length() - 1;
    while (i >= 0 && (data[i] == ' ' || data[i] == '\t' || data[i] == '\n' || data[i] == '\r')) {
        data.remove(i); // Remove the character at position i
        i--;
    }
    return data;
}

bool isValidAction(const String& action)
{
    char buffer[16];
    for (byte i = 0; i < sizeof(validActions) / sizeof(validActions[0]); i++) {
        strcpy_P(buffer, (char*)pgm_read_word(&(validActions[i])));
        if (action.equals(buffer)) {
            return true;
        }
    }
    return false;
}

bool isValidTarget(const String& target)
{
    for (const char* validTarget : validTargets) {
        if (target.equals(validTarget)) {
            return true;
        }
    }
    return false;
}

// Helper function to compare a string against PROGMEM arrays
bool isValidPurity(const char* purity)
{
    char buffer[12];
    for (byte i = 0; i < sizeof(validPurities) / sizeof(validPurities[0]); i++) {
        strcpy_P(buffer, (char*)pgm_read_word(&(validPurities[i]))); // Copy from PROGMEM to RAM
        if (strcasecmp(purity, buffer) == 0) {
            return true;
        }
    }
    return false;
}

bool isValidTarget(const char* target)
{
    char buffer[8];
    for (byte i = 0; i < sizeof(validTargets) / sizeof(validTargets[0]); i++) {
        strcpy_P(buffer, (char*)pgm_read_word(&(validTargets[i])));
        if (strcasecmp(target, buffer) == 0) {
            return true;
        }
    }
    return false;
}

// EEPROM Write (char array)
void writeStringToEEPROM(int addrOffset, const char* strToWrite)
{
    byte len = strlen(strToWrite);
    EEPROM.write(addrOffset, len);
    for (int i = 0; i < len; i++) {
        EEPROM.write(addrOffset + 1 + i, strToWrite[i]);
    }
}

// EEPROM Read (char array)
void readStringFromEEPROM(int addrOffset, char* buffer, int maxLength)
{
    int len = EEPROM.read(addrOffset);
    if (len > maxLength - 1)
        len = maxLength - 1; // Prevent overflow
    for (int i = 0; i < len; i++) {
        buffer[i] = EEPROM.read(addrOffset + 1 + i);
    }
    buffer[len] = '\0'; // Null-terminate the string
}
