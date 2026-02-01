package com.example.utgc;

public interface BinderInterface {

    void MQTTPublish(String topic, String msg);
    void stopMqtt();
}
