import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { View, StyleSheet } from 'react-native';
import { Button, Text, colors, spacing } from '../ui';
import { Ionicons } from '@expo/vector-icons';

type HomeStackParamList = {
  Home: undefined;
  Lesson: { lessonId: string } | undefined;
};

type TabParamList = {
  Learn: undefined;
  Profile: undefined;
};

const HomeStack = createNativeStackNavigator<HomeStackParamList>();
const Tab = createBottomTabNavigator<TabParamList>();

const HomeScreen: React.FC = () => (
  <View style={styles.centered}>
    <Text variant="headline" emphasis="bold">
      Ready for your next lesson?
    </Text>
    <Text color="textSecondary">
      Explore conversation modules curated for your fluency goals.
    </Text>
  </View>
);

const ProfileScreen: React.FC<{ onSignOut: () => void }> = ({ onSignOut }) => (
  <View style={styles.centered}>
    <Text variant="headline" emphasis="bold">
      Profile
    </Text>
    <Text color="textSecondary" style={styles.profileCopy}>
      Track streaks, achievements, and adjust learning preferences.
    </Text>
    <Button label="Sign out" variant="secondary" onPress={onSignOut} style={styles.signOutButton} />
  </View>
);

const HomeStackNavigator: React.FC = () => (
  <HomeStack.Navigator>
    <HomeStack.Screen name="Home" component={HomeScreen} options={{ title: 'Home' }} />
    <HomeStack.Screen
      name="Lesson"
      component={HomeScreen}
      options={{ title: 'Lesson' }}
    />
  </HomeStack.Navigator>
);

interface AppNavigatorProps {
  onSignOut: () => void;
}

export const AppNavigator: React.FC<AppNavigatorProps> = ({ onSignOut }) => (
  <Tab.Navigator
    screenOptions={({ route }) => ({
      headerShown: false,
      tabBarActiveTintColor: colors.primary,
      tabBarInactiveTintColor: colors.textSecondary,
      tabBarIcon: ({ color, size }) => {
        const iconName = route.name === 'Learn' ? 'book' : 'person-circle';
        return <Ionicons name={iconName as const} size={size} color={color} />;
      }
    })}
  >
    <Tab.Screen name="Learn" component={HomeStackNavigator} />
    <Tab.Screen name="Profile">
      {() => <ProfileScreen onSignOut={onSignOut} />}
    </Tab.Screen>
  </Tab.Navigator>
);

const styles = StyleSheet.create({
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24
  },
  profileCopy: {
    textAlign: 'center',
    marginBottom: spacing.lg
  },
  signOutButton: {
    minWidth: 160
  }
});
