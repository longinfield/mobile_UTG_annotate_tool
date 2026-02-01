package com.example.utgc;

import static android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_BACK;
import static android.os.Environment.DIRECTORY_DCIM;

import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.os.Binder;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.util.Base64;
import android.util.Log;
import android.widget.Toast;

import androidx.annotation.Nullable;

import org.eclipse.paho.client.mqttv3.IMqttActionListener;
import org.eclipse.paho.client.mqttv3.IMqttDeliveryToken;
import org.eclipse.paho.client.mqttv3.IMqttToken;
import org.eclipse.paho.client.mqttv3.MqttCallback;
import org.eclipse.paho.client.mqttv3.MqttConnectOptions;
import org.eclipse.paho.client.mqttv3.MqttMessage;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.Random;
import java.util.concurrent.CountDownLatch;
import java.util.regex.Pattern;

import info.mqtt.android.service.Ack;
import info.mqtt.android.service.MqttAndroidClient;

public class MQTTService extends Service {

    public static final String TAG = MQTTService.class.getSimpleName();
    public static String myTopic = "myCloud";
    public static String actionTopic = "BackTopic";

    public static String fileTopic = "fileCallback";

    private final String userName = "admin";
    private final String passWord = "Admin123";

    public MqttAndroidClient client;
    public MqttConnectOptions conOpt;

    private boolean isRunning = false;
    private CountDownLatch latch;
    private CountDownLatch backlatch;

    public class MyBinder extends Binder implements BinderInterface{

        @Override
        public void MQTTPublish(String topic, String msg) {
            publish(topic,msg);
            Log.e("MQTT发送长度",msg.length() + "");
        }

        @Override
        public void stopMqtt() {
            stopSelf();
        }

        public void waitForCallback() {
            latch = new CountDownLatch(1); // Initialize latch
            try {
                latch.await(); // Wait for the callback
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt(); // Restore interrupt status
            }
        }

        public void waitForSmartbackCallback() {
            backlatch = new CountDownLatch(1); // Initialize latch
            try {
                backlatch.await(); // Wait for the callback
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt(); // Restore interrupt status
            }
        }
    }

    public String getCreate_id(){
        String str="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
        Random random=new Random();
        StringBuilder sb=new StringBuilder();
        for(int i=0;i<16;i++){
            int number=random.nextInt(62);
            sb.append(str.charAt(number));
        }

        return sb.toString().trim();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if(isRunning) return START_STICKY;
        isRunning = true;
        String serverAddress="";
//        String serverAddress="";
        String port="1883";
        String clientId = getCreate_id();
//        myTopic = intent.getStringExtra(topicKey);
        String uri = "tcp://"+serverAddress+":"+port;
        client = new MqttAndroidClient(this, uri, clientId, Ack.AUTO_ACK);
        // 设置MQTT监听并且接受消息
        client.setCallback(mqttCallback);
        conOpt = new MqttConnectOptions();
        // 清除缓存
        conOpt.setCleanSession(true);
        // 设置超时时间，单位：秒
        conOpt.setConnectionTimeout(120);
        // 心跳包发送间隔，单位：秒
        conOpt.setKeepAliveInterval(120);//此处如果设置的太小的话，会在读取文件读不完的时候就被停掉，然后重连，那样就收不到回调了
        // 用户名
        conOpt.setUserName(userName);
        // 密码
        conOpt.setPassword(passWord.toCharArray());
        conOpt.setAutomaticReconnect(true);

        // last will message
        boolean doConnect = true;
        String message = "{\"terminal_uid\":\"" + clientId + "\"}";
        String topic ="myCloud";
        int qos = 1;
        boolean retained = false;

        try {
            conOpt.setWill(topic, message.getBytes(), qos, retained);
        } catch (Exception e) {
            Log.i(TAG, "Exception Occurred", e);
            doConnect = false;
            iMqttActionListener.onFailure(null, e);
        }

        if (doConnect) {
            doClientConnection();
        }
        return super.onStartCommand(intent, flags, startId);
    }

    private final MqttCallback mqttCallback = new MqttCallback(){
        @Override
        public void connectionLost(Throwable cause) {
            Log.e("MQTT","失去连接");
            new Handler(Looper.getMainLooper()).post(()->{
                Toast.makeText(MQTTService.this, "失去连接", Toast.LENGTH_SHORT).show();
            });
            cause.printStackTrace();
        }

        @Override
        public void messageArrived(String topic, MqttMessage message) throws Exception {
            String msg = new String(message.getPayload()).replace("\n","");
            Log.e("MQTT " + topic,msg);
            if ("myCloud".equals(topic)) { // Replace with your actual callback topic
                handleRelocateCallbackMessage(message);
            }else if("fileCallback".equals(topic)){
                handlefileCallbackMessage(message);
            }else if(topic.equals(actionTopic)){
                Log.d("status", "tap the next element");
                handleSmartbackCallbackMessage(message);
            }
        }

        @Override
        public void deliveryComplete(IMqttDeliveryToken token) {

        }
    };

    private void handlefileCallbackMessage(MqttMessage message) {
        Log.d("status","文件发送成功");
        latch.countDown(); // Release the latch
    }

    private void handleSmartbackCallbackMessage(MqttMessage message){
        Log.d(TAG, "Callback arrived: " + new String(message.getPayload()));
        //parseJsonData(new String(message.getPayload()));
        String jsonData = new String(message.getPayload()) ;
        try {
            JSONObject jsonObject = new JSONObject(jsonData);
            RecordService.coordinate_x = jsonObject.getInt("coordinate_x");
            RecordService.coordinate_y = jsonObject.getInt("coordinate_y");
        } catch (JSONException e) {
            e.printStackTrace();
        }
        backlatch.countDown(); // Release the latch
    }

    private void handleRelocateCallbackMessage(MqttMessage message) {
        Log.d(TAG, "Callback arrived: " + new String(message.getPayload()));
        //parseJsonData(new String(message.getPayload()));
        String jsonData = new String(message.getPayload()) ;
        try {
            JSONObject jsonObject = new JSONObject(jsonData);
            RecordService.possibleSameScreenNum = jsonObject.getInt("screenNum");
            RecordService.isSame = jsonObject.getBoolean("isSame");
            RecordService.pageFreeze = jsonObject.getBoolean("page_freeze");
            RecordService.new_node_array = jsonObject.getJSONArray("new_node_array");
        } catch (JSONException e) {
            e.printStackTrace();
        }
        latch.countDown(); // Release the latch
    }

    private final IMqttActionListener iMqttActionListener = new IMqttActionListener(){

        @Override
        public void onSuccess(IMqttToken asyncActionToken) {
            Log.i("MQTT","连接成功");
            MQTTHelper.getInstance().setConnected(true);
            client.subscribe(myTopic,1);
            client.subscribe(actionTopic,1);
            client.subscribe(fileTopic,1);

            new Handler(Looper.getMainLooper()).post(()->{
                Toast.makeText(MQTTService.this, "连接成功", Toast.LENGTH_SHORT).show();
            });

            /*测试代码
            MQTTHelper mqttHelper = MQTTHelper.getInstance();
            mqttHelper.getMyBinder().MQTTPublish("textTopic", "hello");
            Log.d(TAG,"已发送");*/
            //mqttHelper.getMyBinder().waitForCallback();
        }

        @Override
        public void onFailure(IMqttToken asyncActionToken, Throwable exception) {
            Log.e("MQTTError","连接失败",exception);
            MQTTHelper.getInstance().setConnected(false);
            doClientConnection();
            new Handler(Looper.getMainLooper()).post(()->{
                Toast.makeText(MQTTService.this, "连接失败", Toast.LENGTH_SHORT).show();
            });
        }
    };

    private void doClientConnection() {
        if (!client.isConnected() && isConnectIsNormal()) {
            client.connect(conOpt, null, iMqttActionListener);
        }

    }

    private boolean isConnectIsNormal() {
        ConnectivityManager connectivityManager =
                (ConnectivityManager) this.getApplicationContext().getSystemService(Context.CONNECTIVITY_SERVICE);
        NetworkInfo info = connectivityManager.getActiveNetworkInfo();
        if (info != null && info.isAvailable()) {
            String name = info.getTypeName();
            Log.i(TAG, "MQTT当前网络名称：" + name);
            return true;
        } else {
            Log.i(TAG, "MQTT 没有可用网络");
            return false;
        }
    }

    public void publish(String topic,String msg){
        int qos = 1;
        boolean retained = false;
        client.publish(topic, msg.getBytes(), qos, retained);
//            Log.i("Send MqttMessage", msg[msg.length-1]);
    }



    @Override
    public void onDestroy() {
        if(client != null){
            try {
                MQTTHelper.getInstance().setConnected(false);
                client.unregisterResources();
                client.close();
                client.disconnect();
                client = null;
                Thread.sleep(1000);
            } catch (Exception e) {
                e.printStackTrace();
            }

        }
        super.onDestroy();
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return new MyBinder();
    }
}
