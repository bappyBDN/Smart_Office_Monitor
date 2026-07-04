#include <Servo.h>

// পিন নাম্বার ডিফাইন করা
const int ledPin1 = 2;     // Red LED
const int ledPin2 = 4;     // Green LED
const int ledPin3 = 5;     // Blue LED
const int relayPin = 3;    // Relay Module

const int servoPin1 = 9;   // First Servo
const int servoPin2 = 10;  // Second Servo

Servo myServo1;            
Servo myServo2;            

void setup() {
  // LED এবং Relay পিনগুলোকে আউটপুট হিসেবে সেট করা
  pinMode(ledPin1, OUTPUT);
  pinMode(ledPin2, OUTPUT);
  pinMode(ledPin3, OUTPUT);
  pinMode(relayPin, OUTPUT);
  
  // Servo দুটিকে আরডুইনোর সাথে যুক্ত করা
  myServo1.attach(servoPin1);
  myServo2.attach(servoPin2);
}

void loop() {
  // ---- স্টেট ১: সব অন এবং Servo ১ (১৮০ ডিগ্রি), Servo ২ (০ ডিগ্রি) ----
  digitalWrite(ledPin1, HIGH);
  digitalWrite(ledPin2, HIGH);
  digitalWrite(ledPin3, HIGH);
  digitalWrite(relayPin, HIGH); // Relay অন
  
  myServo1.write(180);
  myServo2.write(0);
  delay(2000); // ২ সেকেন্ড অপেক্ষা

  // ---- স্টেট ২: সব অফ এবং Servo ১ (০ ডিগ্রি), Servo ২ (১৮০ ডিগ্রি) ----
  digitalWrite(ledPin1, LOW);
  digitalWrite(ledPin2, LOW);
  digitalWrite(ledPin3, LOW);
  digitalWrite(relayPin, LOW);  // Relay অফ
  
  myServo1.write(0);
  myServo2.write(180);
  delay(2000); // ২ সেকেন্ড অপেক্ষা
}