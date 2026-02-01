package com.example.utgc;

public class MQTTHelper {

    private volatile static MQTTHelper instance = null;
    private MQTTService.MyBinder myBinder = null;

    boolean isConnected = false;
    private MQTTHelper(){

    }

    public static MQTTHelper getInstance(){
        if(instance == null){
            synchronized (MQTTHelper.class){
                if(instance == null){
                    instance = new MQTTHelper();
                }
            }
        }
        return instance;
    }

    public boolean isConnected() {
        return isConnected;
    }

    public void setConnected(boolean connected) {
        isConnected = connected;
    }

    public void setMyBinder(MQTTService.MyBinder myBinder) {
        this.myBinder = myBinder;
    }

    public MQTTService.MyBinder getMyBinder() {
        return myBinder;
    }
}
