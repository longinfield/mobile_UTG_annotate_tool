package com.example.utgc;

import static androidx.core.app.ActivityCompat.finishAffinity;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.Path;
import android.graphics.Rect;
import android.os.Binder;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.util.Base64;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

import androidx.core.app.NotificationCompat;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import org.json.JSONTokener;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.FileReader;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.Random;
import java.util.function.ToDoubleFunction;

public class RecordService extends AccessibilityService {

    private static final int MAX_STEPS = 100;
    //private static ToDoubleFunction<? super JSONObject> getArea;

    private JSONObject rootNode;

    private JSONArray nodeArray;
    private JSONArray hierarchyArray;
    private Bitmap screenBitmap;
    private String appDir;
    private String packageName;
    private String className;
    private ArrayList<Integer> indexList;
    private ArrayList<JSONArray> screenList;
    private ArrayList<JSONArray> transGraph;



    private int count;
    private int tempScreen;
    private int tempElement;
    private int screenNum;
    private boolean isExploration;

    private boolean viewClicked;

    private boolean visited;
    public static boolean isStartCrawl;

    private Handler handler;
    private static final String TAG = RecordService.class.getName();

    public static int possibleSameScreenNum;
    public static boolean isSame;
    public static boolean pageFreeze;

    public static JSONArray new_node_array;

    public static int coordinate_x;
    public static int coordinate_y;

    private ExecutorService executor = Executors.newSingleThreadExecutor();

    private int screenWidth;
    private int screenHeight;
    private int dispatchCount;
    private int tempDispatchCount;

    private Handler dispatchCountHandler = new Handler();
    private Runnable dispatchCountRunnable;

    /*
    MQTTService.MyBinder mqttBinder;

    // 用于跟 MQTTService 交互的ServiceConnection
    private ServiceConnection serviceConnection;

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        Log.d(TAG, "onServiceConnected (AccessibilityService)");

        // 1) 准备绑定 MQTTService
        Intent intent = new Intent(this, MQTTService.class);

        // 2) 再 bindService，拿到 Binder
        serviceConnection = new ServiceConnection() {
            @Override
            public void onServiceConnected(ComponentName name, IBinder service) {
                Log.d(TAG, "MQTTService onServiceConnected");
                // 判断类型并保存
                if (service instanceof MQTTService.MyBinder) {
                    MQTTService.MyBinder binder = (MQTTService.MyBinder) service;
                    // 设置到单例 MQTTHelper 中
                    MQTTHelper.getInstance().setMyBinder(binder);

                    // **同时** 更新本地的mqttBinder引用
                    mqttBinder = binder;
                }
            }

            @Override
            public void onServiceDisconnected(ComponentName name) {
                // Service 被系统杀死或出现异常时调用
                Log.d(TAG, "MQTTService onServiceDisconnected");
                MQTTHelper.getInstance().setMyBinder(null);
            }
        };

        // 执行绑定
        bindService(intent, serviceConnection, BIND_AUTO_CREATE);
    }
    */


    public RecordService() {
    }

    @Override
    public void onCreate() {
        super.onCreate();
        count = 0;
        screenNum=0;
        tempElement = -1;
        tempScreen = 0;
        isStartCrawl = false;
        isExploration=false;
        visited = false;
        viewClicked = false;
        SharedPreferences sharedPref = getSharedPreferences("Data", MODE_PRIVATE);
        appDir= sharedPref.getString("collectAppDir", null);
        packageName = sharedPref.getString("package", null);
        className = sharedPref.getString("startClass", null);

        screenList = new ArrayList<JSONArray>();
        transGraph = new ArrayList<JSONArray>();
        indexList = new ArrayList<Integer>();

        WindowManager wm = (WindowManager) this.getSystemService(Context.WINDOW_SERVICE);
        DisplayMetrics displayMetrics = new DisplayMetrics();
        wm.getDefaultDisplay().getMetrics(displayMetrics);

        screenWidth = displayMetrics.widthPixels;
        screenHeight = displayMetrics.heightPixels;

        dispatchCount = 0;
        tempDispatchCount = -1;

    }


    //给定当前页面与上一个页面的序号，找到做返回操作的按钮的位置
    private void smartBack(){
        // 把当前页面和当前页面的前一个页面和本地目录路径发送到mqtt后端，然后后端返回一个做回退点击的坐标就好了
        //screenBitmap = ScreenCaptureImageActivity.getImage();
        //appDir //所有存储的截图的本地目录路
        /*MQTTHelper mqttHelper = MQTTHelper.getInstance();
        //创建健值对
        JSONObject queryData = new JSONObject();
        try {
            queryData.put("packageName", packageName);
            queryData.put("prior", prior); //前一个页面
            queryData.put("current", current);
        } catch (JSONException e) {
            throw new RuntimeException(e);
        }
        mqttHelper.getMyBinder().MQTTPublish("smartBackTopic", queryData.toString());
        Log.d("status","已发送");
        mqttHelper.getMyBinder().waitForSmartbackCallback();

        Log.d("status", "回退坐标"+ String.valueOf(coordinate_x) + ","+String.valueOf(coordinate_y));*/

        if(screenBitmap != null){
            //做好发送截屏的准备工作
            ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
            screenBitmap.compress(Bitmap.CompressFormat.JPEG, 100, outputStream);
            byte[] bytes = outputStream.toByteArray();
            String base64 = "data:image/jpeg;base64," + Base64.encodeToString(bytes,Base64.DEFAULT);
            MQTTHelper mqttHelper = MQTTHelper.getInstance();
            //创建健值对
            JSONObject queryData = new JSONObject();
            try {
                queryData.put("image", base64);
                queryData.put("packageName", packageName);
                queryData.put("text", String.valueOf(count)+"_screenshot.jpg" );
                queryData.put("nodeArray", hierarchyArray.toString());
            } catch (JSONException e) {
                throw new RuntimeException(e);
            }
            mqttHelper.getMyBinder().MQTTPublish("smartBackTopic", queryData.toString());
            Log.d("status","已发送");
            mqttHelper.getMyBinder().waitForSmartbackCallback();

            Log.d("status", "回退坐标"+ String.valueOf(coordinate_x) + ","+String.valueOf(coordinate_y));

        }

    }


    //给定当前页面与访问过的页面列表，通过一一对比两个界面上的文本信息来判断当前界面是否为已经被访问过的界面，若不是则把visited置为false，若是则找到该页面的index并把visited置为true
    private void reLocateScreen(){
        // 把截图和本地目录路径发送到mqtt后端，然后后端返回一个int类型的数值就好了
        //screenBitmap = ScreenCaptureImageActivity.getImage();
        //appDir //所有存储的截图的本地目录路径
        if(screenBitmap != null){
            //做好发送截屏的准备工作
            ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
            screenBitmap.compress(Bitmap.CompressFormat.JPEG, 100, outputStream);
            byte[] bytes = outputStream.toByteArray();
            String base64 = "data:image/jpeg;base64," + Base64.encodeToString(bytes,Base64.DEFAULT);
            MQTTHelper mqttHelper = MQTTHelper.getInstance();
            //创建健值对
            JSONObject queryData = new JSONObject();
            try {
                queryData.put("image", base64);
                queryData.put("packageName", packageName);
                queryData.put("text", String.valueOf(count)+"_screenshot.jpg" );
                queryData.put("nodeArray", nodeArray.toString());
            } catch (JSONException e) {
                throw new RuntimeException(e);
            }
            //判断是否为全局的第一次访问
            if(screenList.size()>0){
                // 不是全局的第一次访问，就先发到后端去做比较，如果后端发现它是新页面会自动把它存下来，如果不是的话就设置visited标志量并更换screenNum
                //MqttMessage message = new MqttMessage(queryData.toString().getBytes());
                mqttHelper.getMyBinder().MQTTPublish("tempScreenTopic", queryData.toString());
                Log.d("status","已发送");
                mqttHelper.getMyBinder().waitForCallback();
                Log.d("status","isSame " + String.valueOf(isSame));
                try {
                    Thread.sleep(500);
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
                if(isSame){ //如果认为是相同页面 (服务端设定为相似度超过90%)
                    screenNum = possibleSameScreenNum;
                    Log.d("status","current screen is the same as screen" + String.valueOf(possibleSameScreenNum));
                    visited = true;
                    nodeArray = new_node_array;
                    screenList.set(screenNum,nodeArray);
                }else if(pageFreeze){
                    screenNum = count;
                    visited =false;
                    nodeArray = new JSONArray();
                }else {
                    screenNum = count;
                    visited =false;
                }
            }else{
                //全局第一次访问直接发到后端
                mqttHelper.getMyBinder().MQTTPublish("screenshotTopic", queryData.toString());
                Log.d("status","已发送");
                mqttHelper.getMyBinder().waitForCallback();
            }
        }

    }

    private void reLocateScreen_original(){
        Log.d("status", "relocate screen");
        /*
        if(screenList.size()>0){
            float maxMatch = 0f;
            int maxIndex = -1;
            for (int i = 0; i<screenList.size(); i++) {
                int matchCount = 0;
                int txtRecord = 0; //所提取的已经访问过的界面中有text的数量
                int txtCurrent = 0;//当前页面中有text的数量
                for(int j = 0; j<screenList.get(i).length();j++){
                    JSONObject temp = null;
                    try {
                        temp = screenList.get(i).getJSONObject(j);
                        String recText = temp.getString("text");
                        txtRecord +=1;
                        txtCurrent = 0;
                        for (int k = 0; k<nodeArray.length();k++){
                            try { String nodeText = nodeArray.getJSONObject(k).getString("text");
                                txtCurrent+=1;
                                if(nodeText.equals(recText)) {
                                    matchCount+=1;
                                }
                            } catch (JSONException exception) {
                                exception.printStackTrace();
                            }
                        }
                    } catch (JSONException exception) {
                        exception.printStackTrace();
                    }
                }
                float match1 = (float)matchCount/txtRecord;
                float match2 = (float)matchCount/txtCurrent;
                float match = Math.min(match1,match2);
                if (match > maxMatch){
                    maxMatch = match;
                    maxIndex = i;
                }
                    //if(matchCount == screenList.get(i).length() && matchCount == nodeArray.length()){
            }
            if(maxMatch >= 0.3){ //如果超过40%的文本一模一样则判断为相同界面 （但是这里有一个问题就是加入购物车之类的操作就前后会被认为是相同页面）
                screenNum = maxIndex;
                Log.d("status","current screen is the same as screen" + String.valueOf(maxIndex));
                visited = true;
                nodeArray = screenList.get(screenNum);
            }
        }*/
        //把当前截屏发到后端，如果是第一次截屏则直接存在后端，如果不是第一次则会判断它是不是新页面如果是的话也会存在后端，如果不是新截屏（即isSame为true）的的话就把visited设置为true，把screenNum换成那个被找到的屏幕的序号

        /*
        if(screenList.size()>0){
            //try{
            //    File directory = new File(appDir);
            //    for(File file : Objects.requireNonNull(directory.listFiles())){
            //    }
            //}catch (Exception e){
            //    Log.e(TAG,"sendError",e);
           //}

            if(screenBitmap != null){
                ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
                screenBitmap.compress(Bitmap.CompressFormat.JPEG, 100, outputStream);
                byte[] bytes = outputStream.toByteArray();
                String base64 = "data:image/jpeg;base64," + Base64.encodeToString(bytes,Base64.DEFAULT);
                MQTTHelper mqttHelper = MQTTHelper.getInstance();
                if(mqttHelper.isConnected && mqttHelper.getMyBinder() != null) {
                    //创建健值对
                    JSONObject queryData = new JSONObject();
                    try {
                        queryData.put("image", base64);
                        queryData.put("packageName", packageName);
                        queryData.put("text", String.valueOf(count)+"_screenshot.jpg" );
                    } catch (JSONException e) {
                        throw new RuntimeException(e);
                    }
                    // 发送健值对到主题
                    //MqttMessage message = new MqttMessage(queryData.toString().getBytes());
                    mqttHelper.getMyBinder().MQTTPublish("tempScreenTopic", queryData.toString());
                    Log.d(TAG,"已发送");
                    mqttHelper.getMyBinder().waitForCallback();
                }
                if(isSame){ //如果认为是相同页面 (服务端设定为相似度超过90%)
                    screenNum = possibleSameScreenNum;
                    Log.d("status","current screen is the same as screen" + String.valueOf(possibleSameScreenNum));
                    visited = true;
                    nodeArray = screenList.get(screenNum);
                }
            }
        }else{
            ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
            screenBitmap.compress(Bitmap.CompressFormat.JPEG, 100, outputStream);
            byte[] bytes = outputStream.toByteArray();
            String base64 = "data:image/jpeg;base64," + Base64.encodeToString(bytes,Base64.DEFAULT);
            MQTTHelper mqttHelper = MQTTHelper.getInstance();
            if(mqttHelper.isConnected && mqttHelper.getMyBinder() != null) {
                //创建健值对
                JSONObject queryData = new JSONObject();
                try {
                    queryData.put("image", base64);
                    queryData.put("packageName", packageName);
                    queryData.put("text",String.valueOf(count)+"_screenshot.jpg" );
                } catch (JSONException e) {
                    throw new RuntimeException(e);
                }
                // 发送健值对到主题
                //MqttMessage message = new MqttMessage(queryData.toString().getBytes());
                mqttHelper.getMyBinder().MQTTPublish("screenshotTopic", queryData.toString());
                //mqttHelper.getMyBinder().waitForCallback();
            }
        }*/
    }

    private boolean isKeyboardVisible(AccessibilityEvent event) {
        AccessibilityNodeInfo source = event.getSource();
        if (source != null) {
            for (int i = 0; i < source.getChildCount(); i++) {
                AccessibilityNodeInfo child = source.getChild(i);
                if (child != null && child.getClassName().toString().contains("InputMethodManager")) {
                    return true;
                }
            }
        }else{
            Log.d("status", "window content change source is null");
        }
        return false;
    }


@Override
    public void onAccessibilityEvent(AccessibilityEvent accessibilityEvent) {
        Log.d("test log", "tttttttt");
        //只要截获click事件就截一张图，确保截图是正常的，然后把viewclick设置为标志量，后面判断的时候都是基于viewclick来判断
        //if (accessibilityEvent.getEventType()== AccessibilityEvent.TYPE_VIEW_CLICKED && isStartCrawl){
        if (accessibilityEvent.getEventType()== AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED && isStartCrawl){
            Log.d("status", "receive inital click");
            screenBitmap = ScreenCaptureImageActivity.getImage();
            if (screenBitmap!=null){
                viewClicked = true;
            }
        }

        //点击了，且窗口发生变化了，就意味着完成了一次交互（感觉就是写的更繁琐了些）
        //if (accessibilityEvent.getEventType() == AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED && viewClicked) {
        if(viewClicked){
            Log.d("status", "receive click, wait 4s");
            viewClicked=false; //如果不把viewclick取消掉，Window contentchange就会直接让后面的程序走不下去
            try {
                Thread.sleep(5000);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
            //等待4秒，等界面加载完毕 try { Thread.sleep(3000); } catch (InterruptedException e) { e.printStackTrace(); }

            //增加一个软键盘检测，如果当前页面调起了软键盘，就执行back
            /*boolean isKeyboardVisible = isKeyboardVisible(accessibilityEvent);
            if (isKeyboardVisible){
                Log.d("status", "keyboard show");
                performGlobalAction(GLOBAL_ACTION_BACK);
                Log.d("status", "keyboard show -> back");
                return;
            }*/

            if (isStartCrawl){
                Log.d("status", "read stored files");
                String appPagesPath = appDir+"/"+"pages.json";
                File pagesFile = new File(appPagesPath);
                String utgPath = appDir+"/"+"utg.json";
                File utgFile = new File(utgPath);
                String indexListPath = appDir+"/"+"indexList.json";
                File indexListfile = new File(indexListPath);
                if (pagesFile.exists() && utgFile.exists() && indexListfile.exists()){
                    try {
                        //读取pages写到screenList里面
                        JSONArray outerArray = loadJSONArrayFromFile(pagesFile);
                        Log.d(TAG, String.valueOf(outerArray));
                        for (int i = 0; i < outerArray.length(); i++) {
                            JSONArray innerArray = outerArray.getJSONArray(i);
                            // Iterate over the inner array (the JSON array containing JSON objects)
                            screenList.add(innerArray);
                        }

                        //读取UTG写到transGraph
                        JSONArray utgOuterArray = loadJSONArrayFromFile(utgFile);
                        Log.d(TAG, String.valueOf(utgOuterArray));
                        for (int i = 0; i < utgOuterArray.length(); i++) {
                            JSONArray innerArray = utgOuterArray.getJSONArray(i);
                            // Iterate over the inner array (the JSON array containing JSON objects)
                            transGraph.add(innerArray);
                        }

                        //读取indexList写到visitProgress里面
                        JSONArray jsonArray = loadJSONArrayFromFile(indexListfile);
                        //JSONArray jsonArray = obj.getArrayli("visitProgress");
                        // Transfer the values to an integer ArrayList
                        for (int i = 0; i < jsonArray.length(); i++) {
                            int value = jsonArray.getInt(i);
                            indexList.add(value);
                        }
                        //indexList = (ArrayList<Integer>) obj.get("visitProgress");

                        count = indexList.size();

                        Log.d(TAG, String.valueOf(indexList));
                    } catch (IOException e) {
                        throw new RuntimeException(e);
                    } catch (JSONException e) {
                        throw new RuntimeException(e);
                    }
                }
                isStartCrawl=false;
                isExploration = true;
                //return;
                Log.d("status", "reload screen list length:" + String.valueOf(screenList.size()));
                Log.d("status", "reload transGraph node number length:" + String.valueOf(transGraph.size()));
                Log.d("status", "reload index list length:" + String.valueOf(indexList.size()));

                isStuck();
            }

            //遍历当前页面的VH节点，提取所有叶子结点到nodeArray, 提取view hierarchy到hierarchyArray
            //AccessibilityNodeInfo source = accessibilityEvent.getSource();
            //Log.d(TAG+"source", String.valueOf(source.getText()));

            Log.d(TAG+"event type", String.valueOf(accessibilityEvent.getEventType()));
            AccessibilityNodeInfo rootNode = getRootInActiveWindow();
            if (rootNode == null) {
                return;
            }
            hierarchyArray = new JSONArray();
            nodeArray = new JSONArray();

            Log.d("status", "get VH and leaf nodes");
            //traverseNode(rootNode);
            //Log.d(TAG, String.valueOf(nodeArray)); //leaf node array
            traverseHierarchy(rootNode);
            try {
                nodeArray = filterElements(hierarchyArray);
            } catch (JSONException e) {
                throw new RuntimeException(e);
            }

            screenBitmap = ScreenCaptureImageActivity.getImage();

            if (screenBitmap != null){
                Log.d("status", "get screenshot");
                isExploration=true;
                viewClicked=false;
            }else{
                isExploration=false;
                viewClicked=true;
            }

            if (isExploration && count<MAX_STEPS){
                //通过一一对比两个界面的视觉信息来判断当前界面是否为已经被访问过的界面, 对比screenList（之前访问过的所有界面的nodeArray）, nodeArray（当前界面nodeArray）, 修改screenNum（当前界面的索引）, visited

                /*测试代码
                MQTTHelper mqttHelper = MQTTHelper.getInstance();
                mqttHelper.getMyBinder().MQTTPublish("textTopic", "hello");
                Log.d(TAG,"已发送");*/
                executor.submit(() -> {
                    reLocateScreen();
                    if (!visited) {
                        Log.d("status", "first visit screen"+String.valueOf(count));
                        try {
                            Thread.sleep(1000);
                        } catch (InterruptedException e) {
                            e.printStackTrace();
                        }
                        JSONArray adjacent = new JSONArray(); //由于当前界面是未访问的，那么访问了以后首先要构建一个邻接链表（存储此页面与其他页面的连接关系，即edge）

                        //screenBitmap = ScreenCaptureImageActivity.getImage();
                        Log.d("status", "got the mediaprojection permission?"+ String.valueOf(screenBitmap==null));
                        Log.d("status", "nodeArray length:"+ String.valueOf(nodeArray.length()));
                        if (screenBitmap!=null){ //gotten the mediaprojection permission
                            Log.d("status", "save screenshot, VH, Leaf, pages");
                            String screenshotPath = appDir+"/"+String.valueOf(count)+"_screenshot.jpg";
                            saveBitmap(screenBitmap,screenshotPath); //存截图
                            //sendBitmap(screenBitmap, String.valueOf(count)+"_screenshot.jpg");

                            String LFPath = appDir+"/"+String.valueOf(count)+"_Leaf.json";
                            saveJsonToFile(nodeArray.toString(),LFPath); //存UI element nodes 截图和json都是以当前页面的number来命名的

                            screenList.add(nodeArray); //把当前screen放入screenlist
                            String appPath = appDir+"/"+"pages.json";
                            saveJsonToFile(screenList.toString(),appPath);//存screenList

                            String VHPath = appDir+"/"+String.valueOf(count)+"_VH.json";
                            saveJsonToFile(hierarchyArray.toString(),VHPath); //存View hierarchy 截图和json都是以当前页面的number来命名的

                            JSONObject edge = new JSONObject(); //和设置头结点（这里用-1代表头结点）
                            try {
                                edge.put("element",-1);
                                edge.put("screen", count);
                                adjacent.put(edge); //把edge放入邻接链表
                                transGraph.add(adjacent);//把本界面的邻接表放入整体的这个list里面，有多少个界面，这个list里就有多少项

                                if(count!=0){ //如果不是第一个界面，则其必然有到达它的上个界面且该界面的索引和点击的element存储在了tempScreen和tempElement中
                                    JSONArray priorArray = transGraph.get(tempScreen); //先通过暂存的界面索引获取transgraph中对应的邻接链表
                                    JSONObject e = new JSONObject(); //和新链接（即该界面点击的element以及到达界面也就是当前界面的索引）
                                    e.put("element",tempElement);
                                    e.put("screen", count);
                                    priorArray.put(e); //把edge放入邻接链表
                                }
                            } catch (JSONException exception) {
                                exception.printStackTrace();
                            }
                            Log.d("status", "save utg");
                            String utgPath = appDir+"/"+"utg.json";
                            saveJsonToFile(transGraph.toString(),utgPath);

                            indexList.add(0); //在当前界面访问的元素的index。由于这里处理的是未访问过的界面，因此目标都是点击0号元素进入下一个界面。如果本界面连0号元素都没有，那么重访问的时候必然也是不会再点它的
                            Log.d("status", "当前访问0号元素");
                            String indexListPath = appDir+"/"+"indexList.json";
                            saveJsonToFile(indexList.toString(),indexListPath); //存储各个页面的访问进度
                            Log.d("status", "save indexList");

                            try {
                                Thread.sleep(2000);
                            } catch (InterruptedException e) {
                                e.printStackTrace();
                            }

                            File LFfile = new File(LFPath);
                            sendFile(LFfile);
                            File pgfile = new File(appPath);
                            sendFile(pgfile);
                            File vhfile = new File(VHPath);
                            sendFile(vhfile);
                            File utgfile = new File(utgPath);
                            sendFile(utgfile);
                            File indexListfile = new File(indexListPath);
                            sendFile(indexListfile);
                        }

                        handler = new Handler(getMainLooper());

                        if(nodeArray.length()>0){ //如果本页面有可交互的文本元素
                            Log.d("status", "start click");
                            try {
                                //JSONObject temp = nodeArray.getJSONObject(0); //点击当前界面的0号元素
                                JSONObject temp = findFirstJsonObjectByLeafNodeId(nodeArray, 0);
                                //if (temp.getString("class").contains("TextView")) {//我们已经确保过提取到nodeArray中的元素必然是有TextView的所以这里的判断可以省去
                                int x = (int)(temp.getInt("boundLeft")+temp.getInt("boundRight"))/2;
                                int y = (int)(temp.getInt("boundTop") + temp.getInt("boundBottom"))/2;

                                tempScreen = count;//暂存当前界面的index，如果是第一次访问该界面，则count应当与界面index是一致的
                                tempElement = 0; //第一次访问该界面，默认先点0号元素

                                count = count+1;
                                //visited = false;//把是否访问过的标签重置为false来为新一轮判断做准备
                                handler.postDelayed(new Runnable() {
                                    @Override
                                    public void run() {
                                        boolean finish = myDispatch(x, y,handler);
                                        Log.d("status", "view click is" + String.valueOf(finish));
                                        Log.d("status", "click position is" + String.valueOf(x) + "___"+ String.valueOf(y));
                                    }
                                }, 20);

                            } catch (JSONException exception) {
                                exception.printStackTrace();
                            }
                        }else{
                            Log.d("status", "no clickable elements, exit");
                                    /*
                                    Intent intent = new Intent();
                                    //intent.setClassName("com.mtr.mtrmobile", "com.mtr.mtrmobile.MTRMobileActivity");
                                    intent.setClassName(packageName, className);
                                    isStartCrawl=true;
                                    startActivity(intent);
                                    visited = false;//把是否访问过的标签重置为false来为新一轮判断做准备
                                    viewClicked = true;
                                    */
                                    /*
                                    stopService(); // 停止服务
                                    sendNotification(); // 发送通知
                                    Intent intent = new Intent(RecordService.this, MainActivity.class);
                                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                                    startActivity(intent);
                                     */

                            // 发送广播通知 Activity
                            //Intent intent = new Intent("com.example.CLOSE_APP");
                            //sendBroadcast(intent);

                            smartBack();

                            screenNum = tempScreen;
                            tempScreen = count;//暂存当前界面的index，如果是第一次访问该界面，则count应当与界面index是一致的
                            tempElement = -2; //tempelement =-2 表示返回操作
                            count = count+1;

                            //performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK);
                            //这里的back需要变成一个smartback,让它能够正确地回到上一页

                            handler.postDelayed(new Runnable() {
                                @Override
                                public void run() {
                                    boolean finish = myDispatch((float)coordinate_x, (float)coordinate_y,handler);
                                    Log.d("status", "view click is" + String.valueOf(finish));
                                    Log.d("status", "back click position is" + String.valueOf(coordinate_x) + "___"+ String.valueOf(coordinate_y));
                                }
                            }, 20);
                            viewClicked = true;

                            //tempElement = -2; //tempelement =-2 表示返回操作
                            //reLocateScreen();
                            //int selfNav = canSelfNav(tempScreen);
                            //if(selfNav!=-1){
                            //    performSelfNav(selfNav);
                            //}
                            //visited = false;//把是否访问过的标签重置为false来为新一轮判断做准备
                        }

                    }else{
                        Log.d("status","重访问了界面screen"+screenNum);
                        Log.d("status","nodearray length"+ String.valueOf(nodeArray.length()));
                        try {
                            Thread.sleep(1000);
                        } catch (InterruptedException e) {
                            e.printStackTrace();
                        }
                        handler = new Handler(getMainLooper());
                        //screenBitmap = ScreenCaptureImageActivity.getImage();
                        if (screenBitmap!=null){ //gotten the mediaprojection permission
                            JSONArray priorArray = transGraph.get(tempScreen); //先通过暂存的界面索引获取transgraph中对应的邻接链表
                            JSONObject e = new JSONObject(); //和新连接（即该界面点击的element以及到达界面也就是当前界面的索引）
                            try {
                                e.put("element",tempElement);
                                e.put("screen", screenNum);
                                priorArray.put(e); //把edge放入邻接链表
                            } catch (JSONException ex) {
                                ex.printStackTrace();
                            }
                            String utgPath = appDir+"/"+"utg.json";
                            saveJsonToFile(transGraph.toString(),utgPath);
                            Log.d("status", "更新utg");
                            File utgfile = new File(utgPath);
                            sendFile(utgfile);

                            int tmp = indexList.get(screenNum); //在这个已经访问过的界面我上次点击的是几号元素
                            tmp = tmp+1; //这次我要点击tmp+1号元素
                            Log.d("status", "当前访问的是元素是"+ String.valueOf(tmp));
                            indexList.set(screenNum,tmp);
                            String indexListPath = appDir+"/"+"indexList.json";
                            saveJsonToFile(indexList.toString(),indexListPath); //存储各个页面的访问进度
                            Log.d("status", "save indexList");
                            File indexListfile = new File(indexListPath);
                            sendFile(indexListfile);

                            if(nodeArray.length()>tmp){//当前界面仍然有需要访问的UI element
                                try {
                                    Log.d("status", "start click");
                                    //JSONObject temp = nodeArray.getJSONObject(tmp); //点击当前界面的下一个元素
                                    JSONObject temp = findFirstJsonObjectByLeafNodeId(nodeArray, tmp);
                                    //if (temp.getString("class").contains("TextView")) {//我们已经确保过提取到nodeArray中的元素必然是有TextView的所以这里的判断可以省去
                                    int x = (int)(temp.getInt("boundLeft")+temp.getInt("boundRight"))/2;
                                    int y = (int)(temp.getInt("boundTop") + temp.getInt("boundBottom"))/2;

                                    tempScreen = screenNum;//暂存当前界面的index，如果是第一次访问该界面，则count应当与界面index是一致的
                                    tempElement = tmp;

                                    //count = count+1; //因为没有访问新界面所以count不自加
                                    handler.postDelayed(new Runnable() {
                                        @Override public void run() {
                                            boolean finish = myDispatch(x, y,handler);
                                            Log.d("status", "view click is" + String.valueOf(finish));
                                            Log.d("status", "click position is" + String.valueOf(x) + "___"+ String.valueOf(y));
                                        }
                                    }, 20);

                                    //}
                                } catch (JSONException exception) {
                                    exception.printStackTrace();
                                }
                            }else{
                                Log.d("status", "all UI element has been clicked, move to any connected screen that has not been fully explored OR backtracking");
                                //当一个页面所有元素都被访问过了，就读取utg的数据，找到当前页面对应的邻接链表，然后找到与当前页面可以到达的，且不是当前页面的页面，点击相应元素进入该页面
                                JSONArray currentArray = transGraph.get(screenNum); //先通过暂存的界面索引获取transgraph中对应的邻接链表
                                JSONArray filteredArray;
                                try {
                                    filteredArray = processJSONArray(currentArray,nodeArray.length());
                                } catch (JSONException ex) {
                                    throw new RuntimeException(ex);
                                }
                                Integer selectedElement =findConnectedScreenRandomly(filteredArray, screenNum);
                                if (selectedElement != null) {//如果此页面没有任何值得探索的下一级页面，则返回
                                    Log.d("status","当前页面已经没有未访问的元素，点击元素，" + String.valueOf(selectedElement) + " 随机进入与其相连的新页面" );
                                    try{
                                        Log.d("status", "start click");
                                        //JSONObject temp = nodeArray.getJSONObject(selectedElement); //点击选定元素
                                        JSONObject temp = findFirstJsonObjectByLeafNodeId(nodeArray, selectedElement);//点击选定元素

                                        //if (temp.getString("class").contains("TextView")) {//我们已经确保过提取到nodeArray中的元素必然是有TextView的所以这里的判断可以省去
                                        int x = (int)(temp.getInt("boundLeft")+temp.getInt("boundRight"))/2;
                                        int y = (int)(temp.getInt("boundTop") + temp.getInt("boundBottom"))/2;

                                        tempScreen = screenNum;//暂存当前界面的index，如果是第一次访问该界面，则count应当与界面index是一致的
                                        tempElement = selectedElement; //到了下一个页面后仍然需要通过tempScreen和tempElement来更新utg，因为有可能之前访问的那个页面有内容更新，这样就相当于又进入了新的页面

                                        handler.postDelayed(new Runnable() {
                                            @Override public void run() {
                                                boolean finish = myDispatch(x, y,handler);
                                                Log.d("status", "view click is" + String.valueOf(finish));
                                                Log.d("status", "click position is" + String.valueOf(x) + "___"+ String.valueOf(y));
                                            }
                                        }, 20);
                                    } catch (JSONException exception) {
                                        exception.printStackTrace();
                                    }
                                } else {
                                    Log.d("status","当前页面已经没有未访问的元素，也没有与之相连的其他需要探索的页面");
                                    Log.d("status", "all UI element has been clicked, no clickable elements, exit this page");

                                        /*
                                        stopService(); // 停止服务
                                        sendNotification(); // 发送通知
                                        Intent intent = new Intent(RecordService.this, MainActivity.class);
                                        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                                        startActivity(intent);*/

                                    //这里做一个三相交换，原因在于：执行back之前screenNum是当前页面的序号，执行back之后需要根据这个序号去更新utg也就是，在back前screenNum对应的链表上增加{element:-2, screen: back后的页面序号}
                                    //所以back前的screenNum存在tempScreen里面，back后需要知道back后的screenNum而这个恰好就是back前的页面的前一个页面，存在了tempScreen里面

                                    smartBack();
                                    int exchange;
                                    exchange = tempScreen;
                                    tempScreen = screenNum;
                                    screenNum = exchange;
                                    tempElement = -2; //tempelement =-2 表示人类执行的跳出和返回操作

                                    //performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK);
                                    //这里的back需要变成一个smartback,让它能够正确地回到上一页
                                    handler.postDelayed(new Runnable() {
                                        @Override public void run() {
                                            boolean finish = myDispatch((float)coordinate_x, (float)coordinate_y,handler);
                                            Log.d("status", "view click is" + String.valueOf(finish));
                                            Log.d("status", "back click position is" + String.valueOf(coordinate_x) + "___"+ String.valueOf(coordinate_y));
                                        }

                                    }, 20);
                                    viewClicked = true;

                                }

                                    /*
                                    Intent intent = new Intent();
                                    //intent.setClassName("com.mtr.mtrmobile", "com.mtr.mtrmobile.MTRMobileActivity");
                                    intent.setClassName(packageName, className);
                                    isStartCrawl=true;
                                    startActivity(intent);
                                    visited = false;//把是否访问过的标签重置为false来为新一轮判断做准备
                                    viewClicked = true;*/

                                    /*
                                    stopService(); // 停止服务
                                    sendNotification(); // 发送通知
                                    Intent intent = new Intent(RecordService.this, MainActivity.class);
                                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                                    startActivity(intent);
                                    */

                                // 发送广播通知 Activity
                                //Intent intent = new Intent("com.example.CLOSE_APP");
                                //sendBroadcast(intent);

                                //performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK);
                                //tempElement = -2; //element =-2 表示返回操作
                                //reLocateScreen();

                                //int selfNav = canSelfNav(tempScreen);
                                //if(selfNav!=-1){
                                //    performSelfNav(selfNav);
                                //}
                                //回到上一个页面，点击未点击的element，尝试递归
                                //如果是因为点击无效导致连续跳转结束，可以手动再点一次
                                //如果当前页面没有可点击的而go back，可以让它原地跳一次
                                //Toast.makeText(this,"此页面完成遍历", Toast.LENGTH_SHORT).show();
                                //点击跳转后accessibility没有捕捉到
                                //visited = false;//把是否访问过的标签重置为false来为新一轮判断做准备
                                //viewClicked = true;
                            }

                        }
                    }
                    // 在rootNode中查找需要点击的控件，并调用performAction方法模拟点击
                    //List<AccessibilityNodeInfo> nodes = rootNode.findAccessibilityNodeInfosByText("电商");
                    //for (AccessibilityNodeInfo node : nodes) {
                    //    node.performAction(AccessibilityNodeInfo.ACTION_CLICK);
                    //}
                    dispatchCount = dispatchCount+1;
                });
            }

        }// else if (viewClicked && isExploration) {
            /*viewClicked=false;
            Log.d("status","点击后界面没有发生变化，相当于重访问当前界面-----重访问了界面screen"+screenNum);
            try {
                Thread.sleep(1000);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
            handler = new Handler(getMainLooper());
            handler.postDelayed(new Runnable() {@Override public void run() {
                screenBitmap = ScreenCaptureImageActivity.getImage();
                if (screenBitmap!=null){ //gotten the mediaprojection permission
                    JSONArray priorArray = transGraph.get(tempScreen); //先通过暂存的界面索引获取transgraph中对应的邻接链表
                    JSONObject e = new JSONObject(); //和新连接（即该界面点击的element以及到达界面也就是当前界面的索引）
                    try {
                        e.put("element",tempElement);
                        e.put("screen", screenNum);
                        priorArray.put(e); //把edge放入邻接链表
                    } catch (JSONException ex) {
                        ex.printStackTrace();
                    }
                    String utgPath = appDir+"/"+"utg.json";
                    saveJsonToFile(transGraph.toString(),utgPath);
                    Log.d("status", "更新utg");

                    int tmp = indexList.get(screenNum); //在这个已经访问过的界面我上次点击的是几号元素
                    tmp = tmp+1; //这次我要点击tmp+1号元素
                    Log.d("status", "当前访问的是元素是"+ String.valueOf(tmp));
                    indexList.set(screenNum,tmp);
                    String indexListPath = appDir+"/"+"indexList.json";
                    //JSONObject visitProgress = new JSONObject();
                    //try {
                    //    visitProgress.put("visitProgress", indexList);
                    //} catch (JSONException ex) {
                    //    throw new RuntimeException(ex);
                    //}
                    saveJsonToFile(indexList.toString(),indexListPath); //存储各个页面的访问进度
                    Log.d("status", "save indexList");


                    if(nodeArray.length()>tmp){//当前界面仍然有需要访问的UI element
                        try {
                            Log.d("status", "start click");
                            JSONObject temp = nodeArray.getJSONObject(tmp); //点击当前界面的下一个元素
                            //if (temp.getString("class").contains("TextView")) {//我们已经确保过提取到nodeArray中的元素必然是有TextView的所以这里的判断可以省去
                            int x = (int)(temp.getInt("boundLeft")+temp.getInt("boundRight"))/2;
                            int y = (int)(temp.getInt("boundTop") + temp.getInt("boundBottom"))/2;

                            tempScreen = screenNum;//暂存当前界面的index，如果是第一次访问该界面，则count应当与界面index是一致的
                            tempElement = tmp;
                            visited = false;//把是否访问过的标签重置为false来为新一轮判断做准备
                            viewClicked = true;

                            //count = count+1; //因为没有访问新界面所以count不自加
                            boolean finish = myDispatch(x, y,handler);
                            Log.d("status", "view click is" + String.valueOf(finish));
                            //}
                        } catch (JSONException exception) {
                            exception.printStackTrace();
                        }
                    }else{
                        Log.d("status", "all UI element has been clicked, go back");
                        performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK);
                        int selfNav = canSelfNav(tempScreen);
                        if(selfNav!=-1){
                            performSelfNav(selfNav);
                        }
                        visited = false;//把是否访问过的标签重置为false来为新一轮判断做准备
                        viewClicked = true;

                        //回到上一个页面，点击未点击的element，尝试递归
                        //如果是因为点击无效导致连续跳转结束，可以手动再点一次
                        //如果当前页面没有可点击的而go back，可以让它原地跳一次
                        //Toast.makeText(this,"此页面完成遍历", Toast.LENGTH_SHORT).show();
                        //点击跳转后accessibility没有捕捉到
                    }
                }
            }
            }, 500);*/
        //}
    }

    private void isStuck(){
        /*if (dispatchCountRunnable != null) {
            return;
        }*/
        dispatchCountRunnable = new Runnable() {
            @Override
            public void run() {
                // 在这里检查条件并决定是否注入动作
                // 例如：
                if (tempDispatchCount == dispatchCount) {
                    Log.d("status", "stuck tempDispatchCount: "+ String.valueOf(tempDispatchCount) + "; dispatchCount: " + String.valueOf(dispatchCount));

                    Log.d("status","重访问了界面screen"+screenNum);
                    Log.d("status","nodearray length"+ String.valueOf(nodeArray.length()));
                    try {
                        Thread.sleep(1000);
                    } catch (InterruptedException e) {
                        e.printStackTrace();
                    }
                    handler = new Handler(getMainLooper());
                    handler.postDelayed(new Runnable() {@Override public void run() {
                        screenBitmap = ScreenCaptureImageActivity.getImage();
                        if (screenBitmap!=null){ //gotten the mediaprojection permission
                            JSONArray priorArray = transGraph.get(tempScreen); //先通过暂存的界面索引获取transgraph中对应的邻接链表
                            JSONObject e = new JSONObject(); //和新连接（即该界面点击的element以及到达界面也就是当前界面的索引）
                            try {
                                e.put("element",tempElement);
                                e.put("screen", screenNum);
                                priorArray.put(e); //把edge放入邻接链表
                            } catch (JSONException ex) {
                                ex.printStackTrace();
                            }
                            String utgPath = appDir+"/"+"utg.json";
                            saveJsonToFile(transGraph.toString(),utgPath);
                            Log.d("status", "更新utg");
                            File utgfile = new File(utgPath);
                            sendFile(utgfile);

                            int tmp = indexList.get(screenNum); //在这个已经访问过的界面我上次点击的是几号元素
                            tmp = tmp+1; //这次我要点击tmp+1号元素
                            Log.d("status", "当前访问的是元素是"+ String.valueOf(tmp));
                            indexList.set(screenNum,tmp);
                            String indexListPath = appDir+"/"+"indexList.json";
                            saveJsonToFile(indexList.toString(),indexListPath); //存储各个页面的访问进度
                            Log.d("status", "save indexList");
                            File indexListfile = new File(indexListPath);
                            sendFile(indexListfile);

                            if(nodeArray.length()>tmp){//当前界面仍然有需要访问的UI element
                                try {
                                    Log.d("status", "start click");
                                    JSONObject temp = nodeArray.getJSONObject(tmp); //点击当前界面的下一个元素
                                    //if (temp.getString("class").contains("TextView")) {//我们已经确保过提取到nodeArray中的元素必然是有TextView的所以这里的判断可以省去
                                    int x = (int)(temp.getInt("boundLeft")+temp.getInt("boundRight"))/2;
                                    int y = (int)(temp.getInt("boundTop") + temp.getInt("boundBottom"))/2;

                                    tempScreen = screenNum;//暂存当前界面的index，如果是第一次访问该界面，则count应当与界面index是一致的
                                    tempElement = tmp;


                                    //count = count+1; //因为没有访问新界面所以count不自加
                                    boolean finish = myDispatch(x, y,handler);
                                    Log.d("status", "view click is" + String.valueOf(finish));
                                    Log.d("status", "click position is" + String.valueOf(x) + "___"+ String.valueOf(y));
                                    //}
                                } catch (JSONException exception) {
                                    exception.printStackTrace();
                                }
                            }else{
                                Log.d("status", "all UI element has been clicked, move to the prior page");
                                //当一个页面所有元素都被访问过了，就读取utg的数据，找到当前页面对应的邻接链表，然后找到与当前页面可以到达的，且不是当前页面的页面，点击相应元素进入该页面
                                JSONArray currentArray = transGraph.get(screenNum);
                                Integer selectedElement =findConnectedScreenRandomly(currentArray, screenNum);
                                if (selectedElement != null) {
                                    Log.d("status","当前页面已经没有未访问的元素，点击元素，" + String.valueOf(selectedElement) + " 随机进入与其相连的新页面" );
                                    try{
                                        Log.d("status", "start click");
                                        JSONObject temp = nodeArray.getJSONObject(selectedElement); //点击选定元素
                                        //if (temp.getString("class").contains("TextView")) {//我们已经确保过提取到nodeArray中的元素必然是有TextView的所以这里的判断可以省去
                                        int x = (int)(temp.getInt("boundLeft")+temp.getInt("boundRight"))/2;
                                        int y = (int)(temp.getInt("boundTop") + temp.getInt("boundBottom"))/2;

                                        tempScreen = screenNum;//暂存当前界面的index，如果是第一次访问该界面，则count应当与界面index是一致的
                                        tempElement = selectedElement; //到了下一个页面后仍然需要通过tempScreen和tempElement来更新utg，因为有可能之前访问的那个页面有内容更新，这样就相当于又进入了新的页面

                                        boolean finish = myDispatch(x, y,handler);
                                        Log.d("status", "view click is" + String.valueOf(finish));
                                        Log.d("status", "click position is" + String.valueOf(x) + "___"+ String.valueOf(y));

                                    } catch (JSONException exception) {
                                        exception.printStackTrace();
                                    }
                                } else {
                                    Log.d("status","当前页面已经没有未访问的元素，也没有与之相连的其他页面");
                                    Log.d("status", "all UI element has been clicked, no clickable elements, finish");
                                    /*
                                    stopService(); // 停止服务
                                    sendNotification(); // 发送通知
                                    Intent intent = new Intent(RecordService.this, MainActivity.class);
                                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                                    startActivity(intent);*/

                                    //这里做一个三相交换，原因在于：执行back之前screenNum是当前页面的序号，执行back之后需要根据这个序号去更新utg也就是，在back前screenNum对应的链表上增加{element:-2, screen: back后的页面序号}
                                    //所以back前的screenNum存在tempScreen里面，back后需要知道back后的screenNum而这个恰好就是back前的页面的前一个页面，存在了tempScreen里面

                                    smartBack();
                                    int exchange;
                                    exchange = tempScreen;
                                    tempScreen = screenNum;
                                    screenNum = exchange;
                                    tempElement = -2; //tempelement =-2 表示返回操作

                                    //performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK);
                                    //这里的back需要变成一个smartback,让它能够正确地回到上一页
                                    boolean finish = myDispatch((float)coordinate_x, (float)coordinate_y,handler);
                                    Log.d("status", "view click is" + String.valueOf(finish));
                                    Log.d("status", "back click position is" + String.valueOf(coordinate_x) + "___"+ String.valueOf(coordinate_y));
                                    viewClicked = true;

                                }
                            }
                        }
                    }
                    }, 50);
                    dispatchCount = dispatchCount+1;
                    tempDispatchCount = tempDispatchCount+1;
                }else{
                    Log.d("status", "tempDispatchCount: "+ String.valueOf(tempDispatchCount) + "; dispatchCount: " + String.valueOf(dispatchCount));
                    tempDispatchCount = dispatchCount;
                }
                // 每隔一段时间再次检查
                //dispatchCountHandler.postDelayed(this, 30000); // 每30秒检查一次
                isStuck();
            }
        };
        dispatchCountHandler.postDelayed(dispatchCountRunnable,130000); // 每65秒检查一次
    }

    //给定一个目标页面索引，和当前页面索引，找到从当前界面可以到达该界面的UI element索引。如果找不到，返回-1
    private int findTargetElement(int curPage, int tarPage){
        int targetIndex = -1;
        for(int i = 0; i<transGraph.get(curPage).length(); i++){
            try {
                JSONObject edge = transGraph.get(curPage).getJSONObject(i);
                if(edge.getInt("screen") == tarPage && edge.getInt("element")>=0){
                    targetIndex = edge.getInt("element");
                    break;
                }
            } catch (JSONException ex) {
                ex.printStackTrace();
            }
        }
        return targetIndex;
    }

    //给定一个页面的索引，判断此页面是否可以原地蹦，如果可以，返回能使它原地蹦的element索引，如果不可以，返回-1
    private int canSelfNav(int pageIndex){
        return findTargetElement(pageIndex,pageIndex);
    }

    //给定一个自我跳转元素的索引，执行原地蹦
    private void performSelfNav(int selfNav){
        try {
            JSONObject temp = screenList.get(tempScreen).getJSONObject(selfNav); //点击自蹦元素
            //if (temp.getString("class").contains("TextView")) {//我们已经确保过提取到nodeArray中的元素必然是有TextView的所以这里的判断可以省去
            int x = (int)(temp.getInt("boundLeft")+temp.getInt("boundRight"))/2;
            int y = (int)(temp.getInt("boundTop") + temp.getInt("boundBottom"))/2;

            //count = count+1; 因为没有访问新界面所以count不自加
            boolean finish = myDispatch(x, y,handler);

            Log.d("finish flag", String.valueOf(finish));

        } catch (JSONException exception) {
            exception.printStackTrace();
        }
        viewClicked = true;
    }

    public boolean myDispatch(float x, float y, Handler handler){
        final int DURATION = 10;

        Path clickPath = new Path();
        if(x <0 ){x = 10;}
        if(y<0){y = 10;}
        clickPath.moveTo(x, y);
        clickPath.lineTo(x, y);
        GestureDescription.StrokeDescription clickStroke =
                new GestureDescription.StrokeDescription(clickPath, 10, DURATION);
        GestureDescription.Builder clickBuilder = new GestureDescription.Builder();
        clickBuilder.addStroke(clickStroke);

        GestureResultCallback Callback = new GestureResultCallback() {
            @Override
            public void onCompleted(GestureDescription gestureDescription) {
                super.onCompleted(gestureDescription);
                System.out.println("dispatch complete");
                Log.d("status", "dispatch complete");
                visited = false;//把是否访问过的标签重置为false来为新一轮判断做准备
                viewClicked = true;
            }

            @Override
            public void onCancelled(GestureDescription gestureDescription) {
                super.onCancelled(gestureDescription);
                System.out.println("dispatch cancel");
                Log.d("status", "dispatch cancel");
            }
        };
        return this.dispatchGesture(clickBuilder.build(), Callback, handler);
    }


    @Override
    public void onInterrupt() {

    }

    public boolean onUnbind(Intent intent) {
        Log.d("status", "Accessibility Service unbind.");
        return super.onUnbind(intent);
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        Log.d("status", "Accessibility Service destroyed.");
    }

    private void traverseHierarchy(AccessibilityNodeInfo node) {
        JSONObject child = new JSONObject();
        Rect bound = new Rect();
        try {
            node.getBoundsInScreen(bound);
            child.put("boundLeft",bound.left);
            child.put("boundTop",bound.top);
            child.put("boundRight",bound.right);
            child.put("boundBottom",bound.bottom);

            child.put("class", node.getClassName());
            child.put("text", node.getText());
            child.put("content-desc", node.getContentDescription());
            child.put("checkable", node.isCheckable());
            child.put("checked", node.isChecked());
            child.put("clickable", node.isClickable());
            child.put("enabled", node.isEnabled());
            child.put("focusable", node.isFocusable());
            child.put("focused", node.isFocused());
            child.put("long-clickable", node.isLongClickable());
            child.put("password", node.isPassword());
            child.put("scrollable", node.isScrollable());
            child.put("selected", node.isSelected());
            hierarchyArray.put(child);
            if (node.getChildCount() > 0) {
                JSONArray children = new JSONArray();
                for (int i = 0; i < node.getChildCount(); i++) {
                    traverseHierarchy(node.getChild(i));
                }
                child.put("children", children);
            }
        } catch (JSONException e) {
            e.printStackTrace();
        } catch (NullPointerException ne){
            ne.printStackTrace();
        }
    }

    // 计算两个元素的交集面积（适配 boundLeft 等为 int 类型）
    private static double calculateInterArea(JSONObject a, JSONObject b) throws JSONException {
        int leftA = a.getInt("boundLeft");
        int topA = a.getInt("boundTop");
        int rightA = a.getInt("boundRight");
        int bottomA = a.getInt("boundBottom");

        int leftB = b.getInt("boundLeft");
        int topB = b.getInt("boundTop");
        int rightB = b.getInt("boundRight");
        int bottomB = b.getInt("boundBottom");

        int interLeft = Math.max(leftA, leftB);
        int interTop = Math.max(topA, topB);
        int interRight = Math.min(rightA, rightB);
        int interBottom = Math.min(bottomA, bottomB);

        if (interLeft >= interRight || interTop >= interBottom) return 0.0;

        return (double) (interRight - interLeft) * (interBottom - interTop);
    }

    // 判断 a 是否完全包含 b（适配 int 类型边界值）
    private static boolean contains(JSONObject a, JSONObject b) throws JSONException {
        int leftA = a.getInt("boundLeft");
        int topA = a.getInt("boundTop");
        int rightA = a.getInt("boundRight");
        int bottomA = a.getInt("boundBottom");

        int leftB = b.getInt("boundLeft");
        int topB = b.getInt("boundTop");
        int rightB = b.getInt("boundRight");
        int bottomB = b.getInt("boundBottom");

        return leftA <= leftB && topA <= topB && rightA >= rightB && bottomA >= bottomB;
    }

    // 计算元素面积（适配 int 类型边界值）
    private static double getArea(JSONObject obj) throws JSONException {
        int w = obj.getInt("boundRight") - obj.getInt("boundLeft");
        int h = obj.getInt("boundBottom") - obj.getInt("boundTop");
        return Math.max((double) w * h, 0.0);
    }

    // 手写冒泡排序：按元素面积从小到大排序（Android兼容，无Comparator依赖）
    private static void sortListByAreaAsc(List<JSONObject> list) throws JSONException {
        // 冒泡排序核心逻辑：相邻元素比较，大的往后移，最终实现从小到大排序
        int n = list.size();
        for (int i = 0; i < n - 1; i++) {
            // 标记是否发生交换，优化排序效率（无交换说明已有序，直接退出）
            boolean swapped = false;
            for (int j = 0; j < n - 1 - i; j++) {
                // 获取相邻两个元素的面积
                double areaJ = getArea(list.get(j));
                double areaJ1 = getArea(list.get(j + 1));

                // 若前一个元素面积 > 后一个，交换两者位置（保证小的在前）
                if (areaJ > areaJ1) {
                    // 交换list中j和j+1位置的元素
                    JSONObject temp = list.get(j);
                    list.set(j, list.get(j + 1));
                    list.set(j + 1, temp);
                    swapped = true;
                }
            }
            // 无交换说明列表已完全有序，跳出外层循环，提升效率
            if (!swapped) {
                break;
            }
        }
    }

    // 主处理函数（核心逻辑不变，替换为手写排序）
    public static JSONArray filterElements(JSONArray input) throws JSONException {
        // 1. 转成 List 方便操作
        List<JSONObject> list = new ArrayList<>();
        for (int i = 0; i < input.length(); i++) {
            list.add(input.getJSONObject(i));
        }

        // 2. 替换Comparator排序：使用手写的冒泡排序（Android兼容）
        sortListByAreaAsc(list);

        // 3. 标记需要删除的元素索引
        Set<Integer> toRemove = new HashSet<>();

        for (int i = 0; i < list.size(); i++) {
            if (toRemove.contains(i)) continue; // 已标记删除，跳过

            JSONObject a = list.get(i);
            double areaA = getArea(a);

            for (int j = i + 1; j < list.size(); j++) {
                if (toRemove.contains(j)) continue; // 已标记删除，跳过

                JSONObject b = list.get(j);
                double areaB = getArea(b);
                double interArea = calculateInterArea(a, b);

                // 跳过无交集的元素，提升效率
                if (interArea <= 0) continue;

                // 核心判断：交集与任意一个元素面积的比值是否 > 0.8
                double ratioA = interArea / areaA;
                double ratioB = interArea / areaB;
                boolean ratioExceed = (ratioA > 0.8) || (ratioB > 0.8);

                // 条件1：比值超过 0.8  或  条件2：存在包含关系
                if (ratioExceed || contains(a, b) || contains(b, a)) {
                    // 始终删除面积更大的元素（排序后 j 对应元素面积 ≥ i 对应元素）
                    toRemove.add(j);
                }
            }
        }

        // 4. 构建结果 JSONArray
        JSONArray result = new JSONArray();
        for (int i = 0; i < list.size(); i++) {
            if (!toRemove.contains(i)) {
                JSONObject temp = list.get(i);
                temp.put("leaf_node_id",i);
                result.put(temp);
            }
        }

        return result;
    }

    public static JSONObject findFirstJsonObjectByLeafNodeId(JSONArray nodeArray, int targetLeafNodeId) throws JSONException {
        // 1. 前置参数合法性校验（仅需校验nodeArray是否为null，int参数无需校验null）
        if (nodeArray == null) {
            return null;
        }

        // 2. 遍历JSONArray，筛选符合条件的JSONObject
        for (int i = 0; i < nodeArray.length(); i++) {
            JSONObject currentObj = nodeArray.getJSONObject(i);

            // 3. 安全校验：字段存在性+类型合法性+值匹配
            if (currentObj.has("leaf_node_id") &&  // 校验字段是否存在
                    currentObj.get("leaf_node_id") instanceof Number &&  // 校验字段类型为数字
                    ((Number) currentObj.get("leaf_node_id")).intValue() == targetLeafNodeId) {  // 匹配int类型目标值

                // 4. 找到第一个匹配项，直接返回
                return currentObj;
            }
        }

        // 5. 遍历结束未找到匹配项，返回null
        return null;
    }

    /*private void traverseNode(AccessibilityNodeInfo node) {
        if(node==null){
            return;
        }
        JSONObject child = new JSONObject();
        if (node.getChildCount() > 0) {
            //JSONArray children = new JSONArray();
            for (int i = 0; i < node.getChildCount(); i++) {
                traverseNode(node.getChild(i));
            }
            //child.put("children", children);
        }else{
            if (node.getClassName()!=null){
                String className = node.getClassName().toString();
                if (node.getText()!=null || className.contains("ImageView")){
                    Rect bound = new Rect();
                    try {
                        node.getBoundsInScreen(bound);
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                            child.put("id",node.getUniqueId());
                        }
                        child.put("boundLeft",bound.left);
                        child.put("boundTop",bound.top);
                        child.put("boundRight",bound.right);
                        child.put("boundBottom",bound.bottom);

                        child.put("class", node.getClassName());
                        child.put("text", node.getText());
                        child.put("content-desc", node.getContentDescription());
                        child.put("checkable", node.isCheckable());
                        child.put("checked", node.isChecked());
                        child.put("clickable", node.isClickable());
                        child.put("enabled", node.isEnabled());
                        child.put("focusable", node.isFocusable());
                        child.put("focused", node.isFocused());
                        child.put("long-clickable", node.isLongClickable());
                        child.put("password", node.isPassword());
                        child.put("scrollable", node.isScrollable());
                        child.put("selected", node.isSelected());
                        if (bound.left>0 && bound.left<screenWidth & bound.right>0 && bound.right<screenWidth && bound.top>0 && bound.top<screenHeight && bound.bottom > 0 && bound.bottom<screenHeight){
                            nodeArray.put(child);
                        }
                    } catch (JSONException e) {
                        e.printStackTrace();
                    }
                }
            }
        }
    }*/

    private static class Candidate {
        Rect r;
        JSONObject obj;
        int area;
        int depth; // 用于稳定排序（可选）
        Candidate(Rect r, JSONObject obj, int depth) {
            this.r = r;
            this.obj = obj;
            this.area = Math.max(0, r.width()) * Math.max(0, r.height());
            this.depth = depth;
        }
    }

    private final ArrayList<Candidate> candidates = new ArrayList<>();
    private final HashSet<String> seenKeys = new HashSet<>();

    // 用于判断是否是一次“根调用”（避免你递归里重复 finalize）
    private boolean inTraversal = false;


    // === 你外部要调用的入口：保持 traverseNode ===
    public void traverseNode(AccessibilityNodeInfo node) {
        if (node == null) return;

        boolean isRootCall = !inTraversal;
        if (isRootCall) {
            // 初始化一次
            inTraversal = true;
            nodeArray = new JSONArray();
            candidates.clear();
            seenKeys.clear();
        }

        // 深度优先遍历：收集候选
        traverseCollect(node, 0);

        if (isRootCall) {
            // 只在根调用结束时做去交叉并写入 nodeArray
            ArrayList<Candidate> kept = filterNoOverlap(candidates);
            for (Candidate c : kept) nodeArray.put(c.obj);

            inTraversal = false;
        }
    }


    // === 内部：递归收集 TextView/ImageView 候选（不收容器） ===
    private void traverseCollect(AccessibilityNodeInfo node, int depth) {
        if (node == null) return;

        // 1) 先递归子节点
        final int n = node.getChildCount();
        for (int i = 0; i < n; i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child != null) {
                traverseCollect(child, depth + 1);
            }
        }

        // 2) 只收 TextView(有 text) 或 ImageView
        CharSequence clsCs = node.getClassName();
        if (clsCs == null) return;
        String cls = clsCs.toString();

        boolean isImage = cls.contains("ImageView");
        boolean isTextView = cls.contains("TextView");

        CharSequence textCs = node.getText();
        boolean hasText = textCs != null && textCs.toString().trim().length() > 0;

        // 如果你也希望把“无 text 但有 content-desc 的 TextView”算进去，改成：
        // CharSequence descCs0 = node.getContentDescription();
        // boolean hasText = (textCs != null && textCs.toString().trim().length() > 0)
        //        || (descCs0 != null && descCs0.toString().trim().length() > 0);

        if (!(isImage || (isTextView && hasText))) return;

        // 3) bounds 过滤：允许 0；排除无尺寸/明显无效
        Rect b = new Rect();
        node.getBoundsInScreen(b);
        if (b.width() <= 1 || b.height() <= 1) return;
        if (b.right <= 0 || b.bottom <= 0) return;

        // 4) 组 JSON（你原字段风格）
        try {
            JSONObject obj = new JSONObject();
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                obj.put("id", node.getUniqueId());
            }
            obj.put("boundLeft", b.left);
            obj.put("boundTop", b.top);
            obj.put("boundRight", b.right);
            obj.put("boundBottom", b.bottom);

            obj.put("class", cls);
            obj.put("text", textCs == null ? JSONObject.NULL : textCs.toString());

            CharSequence descCs = node.getContentDescription();
            obj.put("content-desc", descCs == null ? JSONObject.NULL : descCs.toString());

            obj.put("checkable", node.isCheckable());
            obj.put("checked", node.isChecked());
            obj.put("clickable", node.isClickable());
            obj.put("enabled", node.isEnabled());
            obj.put("focusable", node.isFocusable());
            obj.put("focused", node.isFocused());
            obj.put("long-clickable", node.isLongClickable());
            obj.put("password", node.isPassword());
            obj.put("scrollable", node.isScrollable());
            obj.put("selected", node.isSelected());

            // 5) 去重 key：bounds + class + text + desc
            String key = b.left + "," + b.top + "," + b.right + "," + b.bottom
                    + "|" + cls
                    + "|t:" + (textCs == null ? "" : textCs.toString())
                    + "|d:" + (descCs == null ? "" : descCs.toString());

            if (seenKeys.add(key)) {
                candidates.add(new Candidate(new Rect(b), obj, depth));
            }
        } catch (JSONException e) {
            e.printStackTrace();
        }
    }


    // === 去交叉：小框优先保留 ===
    private ArrayList<Candidate> filterNoOverlap(ArrayList<Candidate> input) {
        ArrayList<Candidate> arr = new ArrayList<>(input);

        // 小框优先；同面积时更靠上靠左优先；再用 depth 做稳定排序
        arr.sort((a, b) -> {
            if (a.area != b.area) return Integer.compare(a.area, b.area);
            if (a.r.top != b.r.top) return Integer.compare(a.r.top, b.r.top);
            if (a.r.left != b.r.left) return Integer.compare(a.r.left, b.r.left);
            return Integer.compare(b.depth, a.depth); // 更深的优先（可选）
        });

        ArrayList<Candidate> kept = new ArrayList<>();
        for (Candidate c : arr) {
            boolean intersects = false;
            for (Candidate k : kept) {
                if (Rect.intersects(c.r, k.r)) {
                    intersects = true;
                    break;
                }
            }
            if (!intersects) kept.add(c);
        }
        return kept;
    }



    public Integer findConnectedScreenRandomly(JSONArray currentArray, int a) {
        ArrayList<Integer> validScreenElements = new ArrayList<>();
        if (currentArray ==null) return null;
        // 遍历 JSONArray
        for (int i = 0; i < currentArray.length(); i++) {
            JSONObject obj = null;
            try {
                obj = currentArray.getJSONObject(i);
                int screen = obj.getInt("screen");
                int element = obj.getInt("element");
                // 检查 screen 值是否不等于 a
                if (screen != a && element>0) {
                    //检查候选screen是否还有未被访问的元素
                    int progress = indexList.get(screen); //在这个已经访问过的界面我已经点到几号元素了

                    JSONArray targetArray = screenList.get(screen);
                    Log.d("status", "候选element是"+ String.valueOf(element) +"将要去往的候选screen是"+String.valueOf(screen) + "候选screen的progress是"+String.valueOf(progress) + "候选screen的元素一共是" + String.valueOf(targetArray.length()));
                    if(progress<targetArray.length()){
                        Log.d("status", "合格element"+ String.valueOf(element) +"合格候选screen是"+String.valueOf(screen) + "合格候选screen的progress是"+String.valueOf(progress) + "合格候选screen的元素一共是" + String.valueOf(targetArray.length()));
                        validScreenElements.add(element);
                    }
                }
            } catch (JSONException e) {
                throw new RuntimeException(e);
            }
        }
        // 检查是否有有效的 screen 值
        if (validScreenElements.isEmpty()) {
            return null; // 或者抛出异常，取决于你的需求
        }
        // 从有效的 screen 值中随机选择一个
        Random random = new Random();
        return validScreenElements.get(random.nextInt(validScreenElements.size()));
    }

    public static JSONArray loadJSONArrayFromFile(File file) throws IOException, JSONException {
        InputStream inputStream = new FileInputStream(file);
        int fileSize = inputStream.available();
        byte[] buffer = new byte[fileSize];
        inputStream.read(buffer);
        inputStream.close();

        String jsonString = new String(buffer, StandardCharsets.UTF_8);
        JSONTokener tokener = new JSONTokener(jsonString);

        return new JSONArray(tokener);
    }

    public static JSONObject loadJSONObjectFromFile(File file) throws IOException, JSONException {
        InputStream inputStream = new FileInputStream(file);
        int fileSize = inputStream.available();
        byte[] buffer = new byte[fileSize];
        inputStream.read(buffer);
        inputStream.close();

        String jsonString = new String(buffer, StandardCharsets.UTF_8);
        return new JSONObject(jsonString);
    }

    private void saveJsonToFile(String json, String path) {
        //String filename = "accessibility.json";
        File file = new File(path);
        FileOutputStream outputStream = null;
        try {
            outputStream = new FileOutputStream(file);
            outputStream.write(json.getBytes());
            outputStream.flush();
        } catch (IOException e) {
            e.printStackTrace();
        } finally {
            try {
                if (outputStream != null) {
                    outputStream.close();
                }
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
    }

    private void sendFile(File file){
        String fileName = file.getName();
        JSONObject jsonObject = new JSONObject();
        try (FileInputStream fileInputStream = new FileInputStream(file)) {
            byte[] fileBytes = new byte[(int) file.length()];
            fileInputStream.read(fileBytes);
            String base64 = Base64.encodeToString(fileBytes, Base64.DEFAULT);
            jsonObject.put("packageName",packageName);
            jsonObject.put("fileName",fileName);
            jsonObject.put("base64",base64.replace("\n",""));
        } catch (IOException e) {
            Log.e(TAG,"readFileError",e);
            //continue;
        } catch (JSONException e) {
            throw new RuntimeException(e);
        }
        MQTTHelper mqttHelper = MQTTHelper.getInstance();
        if(mqttHelper.isConnected && mqttHelper.getMyBinder() != null){
            mqttHelper.getMyBinder().MQTTPublish("fileTopic",jsonObject.toString());
            //mqttHelper.getMyBinder().waitForCallback();
        }
    }

    public static JSONArray processJSONArray(JSONArray currentArray, int n) throws JSONException {
        // 1. 定义容器：存储去重后的 JSONObject，保留顺序
        List<JSONObject> resultList = new ArrayList<>();
        // 2. 定义辅助集合：存储唯一标识（element-screen 拼接），用于快速判断重复
        Set<String> uniqueKeySet = new HashSet<>();

        // 3. 遍历原始 JSONArray，逐元素处理
        for (int i = 0; i < currentArray.length(); i++) {
            JSONObject currentObj = null;
            try {
                currentObj = currentArray.getJSONObject(i);
            } catch (JSONException e) {
                throw new RuntimeException(e);
            }

            // 跳过非 JSONObject 类型（容错处理）
            if (currentObj == null) {
                continue;
            }

            // 4. 过滤：获取 element 值，仅保留 element < n 的元素
            // 容错处理：若 element 不存在或非数字类型，默认按 -1 处理（可根据需求调整）
            int element = currentObj.optInt("element", -1);
            if (element >= n) {
                continue; // 不符合过滤条件，直接跳过
            }

            // 5. 去重：构造唯一标识（element 和 screen 拼接）
            int screen = currentObj.optInt("screen", 0);
            String uniqueKey = element + "-" + screen;

            // 6. 判断是否重复：未重复则加入结果集和唯一标识集合
            if (!uniqueKeySet.contains(uniqueKey)) {
                // 存入唯一标识，用于后续重复判断
                uniqueKeySet.add(uniqueKey);
                // 存入结果列表，保留原始顺序
                resultList.add(new JSONObject(currentObj.toString())); // 深拷贝，避免修改原始对象
            }
        }

        // 7. 将 List<JSONObject> 转换为 JSONArray 并返回
        JSONArray resultArray = new JSONArray();
        for (JSONObject jsonObj : resultList) {
            resultArray.put(jsonObj);
        }
        return resultArray;
    }


    private void sendBitmap(Bitmap bitmap, String name){
        ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
        bitmap.compress(Bitmap.CompressFormat.JPEG, 100, outputStream);
        byte[] bytes = outputStream.toByteArray();
        String base64 = "data:image/jpeg;base64," + Base64.encodeToString(bytes,Base64.DEFAULT);
        MQTTHelper mqttHelper = MQTTHelper.getInstance();
        if(mqttHelper.isConnected && mqttHelper.getMyBinder() != null) {
            //创建健值对
            JSONObject queryData = new JSONObject();
            try {
                queryData.put("image", base64);
                queryData.put("packageName", packageName);
                queryData.put("text", name);
            } catch (JSONException e) {
                throw new RuntimeException(e);
            }
            // 发送健值对到主题
            //MqttMessage message = new MqttMessage(queryData.toString().getBytes());
            mqttHelper.getMyBinder().MQTTPublish("screenshotTopic", queryData.toString());
        }

    }

    public void stopService() {
        disableSelf();  // 停止 Accessibility Service

    }
    private void sendNotification() {
        NotificationManager notificationManager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        String NOTIFICATION_CHANNEL_ID = "channel_id";

        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    NOTIFICATION_CHANNEL_ID,
                    "Notification Channel",
                    NotificationManager.IMPORTANCE_DEFAULT
            );
            notificationManager.createNotificationChannel(channel);
        }

        NotificationCompat.Builder notificationBuilder = new NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID);
        notificationBuilder.setAutoCancel(true)
                .setDefaults(Notification.DEFAULT_ALL)
                .setWhen(System.currentTimeMillis())
                .setSmallIcon(R.mipmap.ic_launcher) // 设置通知小图标
                .setTicker("Ticker") // 设置状态栏的标题
                .setContentTitle("Session Complete") // 设置通知标题
                .setContentText("Your data collection session is complete.") // 设置通知内容
                .setContentInfo("Info");

        notificationManager.notify(1, notificationBuilder.build());
    }

    private void saveBitmap(Bitmap bitmap, String path) {
        //String filename = "screenshot.png";
        File file = new File(path);
        FileOutputStream outputStream = null;
        try {
            outputStream = new FileOutputStream(file);
            bitmap.compress(Bitmap.CompressFormat.JPEG, 100, outputStream);
            outputStream.flush();
        } catch (IOException e) {
            e.printStackTrace();
        } finally {
            try {
                if (outputStream != null) {
                    outputStream.close();
                }
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
    }


}